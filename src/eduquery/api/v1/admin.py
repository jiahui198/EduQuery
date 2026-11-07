"""
本模块用于设计管理员的知识库管理接口：
    上传文件入库
    网页 URL 入库
    文档列表
    删除文档（连同切片与向量）
    重建索引
"""
import asyncio
import uuid
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, UploadFile, File, Form, Depends, status, BackgroundTasks, Query
from sqlalchemy import func, delete,select
from sqlalchemy.ext.asyncio import AsyncSession

from eduquery.core.db import get_db
from eduquery.core.exceptions import BizException, NotFoundError
from eduquery.models import KnowledgeDoc, KnowledgeChunk
from eduquery.rag import fetcher, retrievers
from eduquery.schemas.knowledge import (
    IngestResult, IngestUrlRequest, CrawlAccepted, CrawlRequest, DocListOut, DocOut
)
from eduquery.models.user import Admin
from eduquery.core.deps import  get_current_admin
from eduquery.core.config import settings
from eduquery.services import ingest_service
from eduquery.rag import vectorstore as vs



router = APIRouter(prefix="/admin/docs",tags=["admin"])


@router.post("/upload",response_model=IngestResult,summary="上传文档并入库")
async def upload_doc(
        file:Annotated[UploadFile,File(description="文档上传参数，支持txt/docx/pdf/md")],
        _ :Annotated[Admin,Depends(get_current_admin)],
        category:Annotated[str|None,Form()]=None,
        title:Annotated[str|None,Form()]=None
)->IngestResult:
    """
    管理员上传单个文档，同步完成解析、切分、向量化与入库
    :param file:流式上传的文件
    :param category:文件分类
    :param title:文件标题
    :param _:注入，管理员信息
    :return:入库结果出参
    """
    #提取文件后缀
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in settings.UPLOAD_ALLOWED_EXT:
        raise BizException(
            f"不支持的文件格式{suffix or '无扩展名'}，"
            #sorted取出字典中元素，升序排序形成列表
            f"请上传 {'/'.join(sorted(settings.UPLOAD_ALLOWED_EXT))}"
        )
    #upload_max_mb设置的为20，转换后为20971520Bytes
    limit = settings.UPLOAD_MAX_MB*1024*1024

    #分块读入内存并放入buf字节数组中
    #空的字节数组
    buf=bytearray()
    while chunk := await file.read(1024*1024):
        buf.extend(chunk)
        if len(buf)>limit:
            raise BizException(f"文件超过{settings.UPLOAD_MAX_MB}MB上限")
    if not buf:
        raise BizException("上传的文件为空")

    #落盘
    settings.UPLOAD_DIR.mkdir(parents=True,exist_ok=True)
    dest = settings.UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    #异步将文件写入到磁盘，不阻塞主线程
    await asyncio.to_thread(dest.write_bytes, bytes(buf))

    #入库
    try:
        result = await ingest_service.ingest_file(
            file_path=str(dest),
            title=title,
            category=category,
            original_name=file.filename
        )
    except Exception as e:
        #入库失败，刚落盘的文件没有价值，删掉免得 data/uploads 里堆垃圾
        await asyncio.to_thread(lambda: dest.unlink(missing_ok=True))
        raise BizException(f"入库失败：{e}")
    return IngestResult(**result, title=title or Path(file.filename or "").stem)


@router.post("/url",response_model=IngestResult,summary="网页入库")
async def ingest_url(
        data:IngestUrlRequest,
        _:Admin = Depends(get_current_admin),
)->IngestResult:
    """
    管理员提交网页地址，系统抓取正文后入库
    """
    try:
        result = await ingest_service.ingest_url(
            data.url,
            data.category,
            force=data.force
        )
    except Exception as e:
        raise BizException(f"入库失败：{e}")
    return IngestResult(**result)


@router.post("/crawl",response_model=CrawlAccepted,
             status_code=status.HTTP_202_ACCEPTED,summary="栏目批量抓取入库（后台执行）")
async def crawl_list(
        data:CrawlRequest,
        background:BackgroundTasks,
        _:Admin = Depends(get_current_admin),
)->CrawlAccepted:
    """
        从官网栏目列表页批量抓取文章入库。
        本接口只做"发现链接"（一次网络请求），真正的抓正文/切分/向量化
        丢到后台任务里跑，立刻返回 202，避免请求超时。
        进度用 GET /admin/docs?status=processing 观察，失败的文档 status=failed。

        :param data: 栏目地址、抓取篇数上限、分类、是否强制重建
        :param background: FastAPI 后台任务
    """
    try:
        urls = await fetcher.list_article_urls(data.list_url, limit=data.limit)
    except Exception as e:
        raise BizException(f"栏目页抓取失败：{e}")

    if not urls:
        raise BizException(
            "没有找到文章链接"
        )

    #后台任务，批量的打包入库
    background.add_task(ingest_service.ingest_files, urls, data.category, data.force)
    return CrawlAccepted(
        discovered=len(urls),
        urls=urls,
        message=f"已提交 {len(urls)} 篇，后台处理中，可通过 /admin/docs 查看进度",
    )


@router.get("",response_model=DocListOut,summary="文档列表（分页+筛选）")
async def list_docs(
        page:int = Query(1,ge=1),
        size:int = Query(10,ge=1,le=100),
        status_:str|None = Query(None,alias="status",description="pending/processing/ready/failed"),
        category:str|None = Query(None),
        db:AsyncSession = Depends(get_db),
        _:Admin = Depends(get_current_admin),
)->DocListOut:
    """
    定义管理员接口，分页列出知识库文档
    """
    conds=[]
    if status_:
        conds.append(KnowledgeDoc.status==status_)
    if category:
        conds.append(KnowledgeDoc.category == category)
    total = (
        await db.execute(select(func.count()).select_from(KnowledgeDoc).where(*conds))
    ).scalar() or 0

    rows = (
        await db.execute(
            select(KnowledgeDoc)
            .where(*conds)
            .order_by(KnowledgeDoc.id.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
    ).scalars().all()
    return DocListOut(
        total=total, page=page, size=size,
        items=[DocOut.model_validate(r) for r in rows],
    )


@router.delete("/{doc_id}",status_code=status.HTTP_204_NO_CONTENT,summary="删除文档")
async def delete_doc(
        doc_id:int,
        db:AsyncSession=Depends(get_db),
        _:Admin=Depends(get_current_admin)
)->None:
    """
    定义管理员接口，删除文档,通过文档id删除文档
    :param doc_id: 文档id
    :param db: 数据库连接session
    :return:
    """
    doc = await db.get(KnowledgeDoc,doc_id)
    if doc is None:
        raise NotFoundError("文档")

    #先记下落盘路径，删完表里就查不到了
    file_path = doc.file_path

    #1.删除向量
    vs.delete_by_doc(doc_id)

    #2.删chunk表
    await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id==doc_id))

    #3.删doc表
    await db.execute(delete(KnowledgeDoc).where(KnowledgeDoc.id==doc_id))
    await db.commit()

    #4.删磁盘原件
    if file_path:
        await asyncio.to_thread(lambda: Path(file_path).unlink(missing_ok=True))

    await retrievers.rebuild_retriever()
    return None

