"""
定义知识库入库主流程：
    网页资源爬取->清洗->切分->入库
"""
from loguru import logger
from sqlalchemy import select,delete
from eduquery.models.knowledge import KnowledgeDoc, KnowledgeChunk

from eduquery.core.db import async_session_maker
from eduquery.rag import retrievers
from eduquery.rag import vectorstore as vs
from eduquery.rag.cleaner import clean_text
from eduquery.rag.embedder import embed_texts
from eduquery.rag.fetcher import fetch_article
from eduquery.rag.splitter import split_text

#新增文件上传功能
import asyncio
from pathlib import Path
from eduquery.upfile.parser import parse_file


async def _index_text(session,doc:KnowledgeDoc,text:str,
                      source_url:str|None,file_path:str|None)->int:
    """
    把已清洗的正文切片、向量化，并双写入 Milvus 与 MySQL 的切片表。
    """
    #1.切分
    docs = split_text(text,{"title":doc.title,"source_url":source_url or ""})
    if not docs:
        raise ValueError("切分结果为空")

    #2.向量化
    vectors = await embed_texts([d.page_content for d in docs])
    vs.ensure_collection()

    ids = vs.insert_chunks(
        [
            {
                "vector": v,
                "doc_id": doc.id,
                "chunk_index": d.metadata["chunk_index"],
                "text": d.page_content[:4000],
                "title": doc.title[:500],
                "source_url": source_url or "",
            }
            for d, v in zip(docs, vectors)
        ]
    )

    session.add_all(
        [
            KnowledgeChunk(
                doc_id=doc.id,
                chunk_index=d.metadata["chunk_index"],
                content=d.page_content,
                vector_id=str(vid),
            )
            for d, vid in zip(docs, ids)
        ]
    )
    doc.chunk_count=len(docs)
    return len(docs)



async def ingest_url(url:str,category:str|None=None,force:bool=False,rebuild:bool=True)->dict:
    """
    定义函数传入url，检索url中的内容，经过清洗切分后填入KnowledgeDoc,KnowledgeChunk两张表中,
    并存入向量数据库

    :param url: 爬取到的url
    :param category:文档分类
    :return:KnowledgeDoc主键id,chunks切分数量
    """

    async with async_session_maker() as session:
        # 查重，根据传过来的url查询数据库，若数据库中有则对其不进行落库和向量化处理
        existing=(
            await  session.execute(
                   select(KnowledgeDoc)
                   .where(KnowledgeDoc.source_url==url)
                )
            ).scalar_one_or_none()

        if existing and existing.status == "ready" and not force:
            logger.info("跳过（已经被入库）:{}",url)
            return {"doc_id":existing.id,"chunks":existing.chunk_count,"skipped":True}

        #1.处理文档状态不为ready的文档：pending(行建好了，还没开始处理)、processing（处理到一半断了）、failed（明确失败）
        if existing:
            doc = existing
            doc.title,doc.status,doc.error_msg = doc.title or url,"pending",None
            await session.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id)
        )
            vs.delete_by_doc(doc.id)

        #2.确认KnowledgeDoc中不存在此url，则向里面添加
        else:
            doc = KnowledgeDoc(
                source_type="web",
                source_url=url,
                category=category,
                status="pending",
                title=url
            )
            session.add(doc)
            await session.commit()
            await session.refresh(doc)      #手动更新表

        #存入KnowledgeDoc后接着存入KnowledgeChunk表中
        try:
            doc.status = "processing"
            await session.commit()

            #1.抓取+清洗
            article = await fetch_article(url)     #获取title,url,raw_text键组成的字典
            doc.title =article["title"] or doc.title
            text = clean_text(article["raw_text"])
            if not text:
                raise ValueError("清洗后正文为空")

            n = await _index_text(session,doc,text,url,None)

            doc.status="ready"
            await session.commit()
            if rebuild:
                await retrievers.rebuild_retriever()
            logger.info("入库完成：{}|{}块|doc_id={}",doc.title,n,doc.id)
            return {"doc_id":doc.id,"chunks":n,"skipped":False}

        except Exception as e :
            await session.rollback()
            doc.status = "failed"
            doc.error_msg = str(e)[:500]
            await session.commit()
            logger.info("入库失败:{}|{}",url,e)
            raise


async def ingest_urls(urls:list[str],category:str|None=None)->list[dict]:
    """
    批量对检索出来的url进行处理

    :param urls: 检索到的url列表
    :param category: 文档分类
    :return: list[dict]
    """
    results = []
    for url in urls:
        try:
            results.append(await ingest_url(url,category))
        except Exception as e:
            results.append({"url":url,"error":str(e)})
    return results


async def ingest_file(file_path:str,title:str|None=None,category:str|None=None,
                      original_name:str|None=None)->dict:
    """
    定义上传文件函数主流程：解析->清洗->切分->向量化->双写->重建BM25
    :param file_path:文件绝对路径
    :param title:指定标题
    :param category:文档分类
    :param original_name:原始文件
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    #上传落盘用的是 uuid 文件名，标题兜底必须回退到原始文件名，否则会落一串 hex
    fallback = Path(original_name).stem if original_name else p.stem
    doc_title = (title or fallback)[:255]

    async with async_session_maker() as session:
        stmt = select(KnowledgeDoc).where(
            KnowledgeDoc.source_type=="upload",
            KnowledgeDoc.title ==doc_title
        )
        existing=(
            await session.execute(stmt)
        ).scalar_one_or_none()

        #判断，没有成功落入向量数据库的情况
        if existing:
            doc=existing
            doc.status, doc.error_msg = "pending", None
            doc.category = category or doc.category
            old_path = doc.file_path
            doc.file_path = file_path      #重传换了新的落盘文件，路径要跟着更新

            #删除chunk表上内容
            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id)
            )

            #删除向量表有关内容
            vs.delete_by_doc(doc.id)
            await session.commit()
            logger.info("同名文档已存在，清旧重建：{}", doc_title)

            #旧的那份落盘文件已经没人引用了，删掉
            if old_path and old_path != file_path:
                await asyncio.to_thread(lambda: Path(old_path).unlink(missing_ok=True))

        #正常落库流程
        else:
            doc = KnowledgeDoc(
                title=doc_title,
                source_type="upload",
                file_path=file_path,
                category=category,
                status="pending"
            )
            session.add(doc)
            await session.commit()

        try:
            doc.status="processing"
            await session.commit()

            #解析
            parsed = await asyncio.to_thread(parse_file,p)
            #doc_title 已做过兜底（title -> 原始文件名 -> 落盘名），不要再被 parsed["title"]（uuid）覆盖
            doc.title = doc_title

            #清洗
            text = clean_text(parsed["text"])
            if not text:
                raise ValueError("解析后正文为空")

            #切分->向量化->写入两张表
            n = await _index_text(session,doc,text,None,file_path)

            doc.status = "ready"
            await session.commit()

            await retrievers.rebuild_retriever()
            logger.info("文件入库完成：{}|{}块|doc_id={}", doc.title, n, doc.id)
            return {"doc_id": doc.id, "chunks": n, "skipped": False}
        except Exception as e :
            await session.rollback()
            doc.status="failed"
            doc.error_msg=str(e)[:500]
            await session.commit()
            logger.exception("文件入库失败：{}",original_name or file_path)
            raise


async def ingest_files(urls:list[str],category:str|None=None,
                     force:bool=False)->list[dict]:
    """
    批量入库上传的文件文档
    :param urls: 栏目页解析出的文章链接列表
    :param category:统一分类
    :param force:true 则已入库的也重建
    """
    results =[]
    for i,url in enumerate(urls,1):
        try:
            r = await ingest_url(url, category, force=force, rebuild=False)
            results.append(r)
        except Exception as e:
            results.append({"url": url, "error": str(e)})
            logger.warning("批量入库 [{}/{}] 跳过 {}：{}", i, len(urls), url, e)
    try:
        await retrievers.rebuild_retriever()
        logger.info("批量入库成功，已重建索引")
    except Exception:
        logger.exception("批量入库后重建 BM25 失败，关键词检索可能暂时不准")
    return results







