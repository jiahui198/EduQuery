"""
本模块用于设计知识库上传管理端的出入参数据模型
"""
from datetime import datetime

from pydantic import BaseModel,Field,ConfigDict

class DocOut(BaseModel):
    """
    定义文档元数据出参模型
    """
    model_config = ConfigDict(from_attributes=True)

    id:int
    title:str
    source_type:str|None=None
    source_url:str|None=None
    file_path:str|None=None
    category:str|None=None
    status:str
    chunk_count:int
    error_msg:str|None=None
    created_at:datetime
    updated_at:datetime


class DocListOut(BaseModel):
    """
    定义文档列表分页出参模型
    """
    total:int
    page:int
    size:int
    items:list[DocOut]


class IngestUrlRequest(BaseModel):
    """
    定义网页入口入参模型
    """
    url:str =Field(...,min_length=8,max_length=1024,description="要入库的网页地址")
    category:str|None=Field(None,max_length=64,description="文档分类，如 规章/通知")
    force:bool=Field(False,description="true 则忽略“已入库”判断，强制重建")


class IngestResult(BaseModel):
    """
    定义入库结果的出参模型
    """
    doc_id:int
    chunks:int
    skipped:bool=False
    title:str|None=None


class CrawlRequest(BaseModel):
    """
    定义批量抓取入参数据模型
    """
    list_url: str = Field(..., min_length=8, max_length=1024, description="栏目列表页地址")
    limit: int = Field(20, ge=1, le=30, description="最多抓取篇数，上限 30")
    category: str | None = Field(None, max_length=64, description="统一分类")
    force: bool = Field(False, description="true 则已入库的文章也强制重建")


class CrawlAccepted(BaseModel):
    """批量抓取受理结果（202，真正的入库在后台跑）"""
    accepted:bool = True
    discovered:int                     #栏目页发现的文章数
    urls:list[str]                     #发现的链接（便于管理员核对抓得对不对）
    message:str