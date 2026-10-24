"""
知识库两张表：文档元数据+切片元数据
"""
from datetime import datetime

from sqlalchemy import DateTime,ForeignKey,Integer,String,Text,func
from sqlalchemy.orm import Mapped,mapped_column,relationship

from eduquery.models.base import Base

class KnowledgeDoc(Base):
    """
    一篇原始文档 = 一个网页，或一个上传的文件
    """
    __tablename__ = "knowledge_doc"

    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    title:Mapped[str] = mapped_column(String(255),nullable=False)

    #文件类型web/upload
    source_type:Mapped[str] = mapped_column(String(32),nullable=False)
    #来源两种：网页source_url，文件file_path
    source_url:Mapped[str|None] = mapped_column(String(1024),nullable=True)
    file_path :Mapped[str|None] = mapped_column(String(512),nullable=True)

    #数据分类：规章、师资、课程、通报文件
    category:Mapped[str|None] = mapped_column(String(64),nullable=True)

    status:Mapped[str|None] = mapped_column(String(16),default="pending",nullable=False)
    chunk_count:Mapped[int] = mapped_column(Integer,default=0,nullable=False)
    error_msg : Mapped[str|None] = mapped_column(Text,nullable=True)

    created_at:Mapped[datetime] = mapped_column(DateTime,server_default=func.now(),nullable=False)
    updated_at:Mapped[datetime] = mapped_column(
        DateTime,server_default=func.now(),onupdate=func.now(),nullable=False
    )

    #knowledge与knowledgechunk表之间建立一对多关系
    chunks:Mapped[list["KnowledgeChunk"]] = relationship(
        back_populates="doc",cascade="all,delete-orphan"
    )

class KnowledgeChunk(Base):
    """
    文档切片后的文本：数据包含=一段文本+它在milvus里的向量ID
    """
    __tablename__ = "knowledge_chunk"

    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)

    doc_id:Mapped[int] = mapped_column(
        ForeignKey("knowledge_doc.id",ondelete="CASCADE"),nullable=False,index=True
    )
    chunk_index:Mapped[int] = mapped_column(Integer,nullable=False)
    content:Mapped[str] = mapped_column(Text,nullable=False)
    vector_id:Mapped[str|None] = mapped_column(String(64),nullable=True)

    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
    doc:Mapped["KnowledgeDoc"] = relationship(back_populates="chunks")


