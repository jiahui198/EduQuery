"""
定义知识库入库主流程：
    网页资源爬取->清洗->切分->入库
"""
from loguru import logger
from sqlalchemy import select,delete
from eduquery.models.knowledge import KnowledgeDoc, KnowledgeChunk

from eduquery.core.db import async_session_maker
from eduquery.rag import vectorstore as vs
from eduquery.rag.cleaner import clean_text
from eduquery.rag.embedder import embed_texts
from eduquery.rag.fetcher import fetch_article
from eduquery.rag.splitter import split_text

async def ingest_url(url:str,category:str|None=None)->dict:
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

        if existing and existing.status == "ready":
            logger.info("跳过（已经被入库）:{}",url)
            return {"doc_id":existing.id,"chunks":existing.chunk_count,"skipped":True}

        #1.处理文档状态不为ready的文档：pending(行建好了，还没开始处理)、processing（处理到一半断了）、field（明确失败）
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

        try:
            doc.status = "processing"
            await session.commit()

            #1.抓取+清洗
            article = await fetch_article(url)     #获取title,url,raw_text键组成的字典
            doc.title =article["title"] or doc.title
            text = clean_text(article["raw_text"])
            if not text:
                raise ValueError("清洗后正文为空")

            #2.切分 元数据metadata传入chunk_index,title,source_url字段,返回document对象
            docs = split_text(text,{"title":doc.title,"source_url":url})
            if not docs:
                raise ValueError("切分结果为空")

            #3.向量化
            vectors = await embed_texts([d.page_content for d in docs])

            #4.存入milvus向量集合中
            vs.ensure_collection()
            ids = vs.insert_chunks(
                [
                    {
                        "vector":v,
                        "doc_id":doc.id,
                        "chunk_index":d.metadata["chunk_index"],
                        "text":d.page_content[:4000],
                        "title":doc.title[:500],
                        "source_url":url,
                    }
                    for d,v in zip(docs,vectors)
                ]
            )

            #5.存入MySQL的knowledgeChunk切片表中
            session.add_all(
                [
                    KnowledgeChunk(
                        doc_id=doc.id,
                        chunk_index=d.metadata["chunk_index"],
                        content = d.page_content,
                        vector_id=str(vid)
                    )
                    for d,vid in zip(docs,ids)
                ]
            )
            doc.chunk_count = len(docs)
            doc.status="ready"
            await session.commit()
            logger.info("入库完成：{}|{}块|doc_id={}",doc.title,len(docs),doc.id)
            return {"doc_id":doc.id,"chunks":len(docs),"skipped":False}

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



