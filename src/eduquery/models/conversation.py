"""
本模块将构建会话表+消息表
用于实现：上下文压缩、长短期记忆
"""
from eduquery.models.base import Base
from sqlalchemy import DateTime,ForeignKey,Integer,String,Text,func
from sqlalchemy.orm import Mapped,mapped_column,relationship
from datetime import datetime

class Conversation(Base):
    """
    会话表，用户的完整会话历史
    """
    __tablename__ = "conversations"

    id :Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)

    student_id:Mapped[int|None] = mapped_column(
        ForeignKey("students.id",ondelete="CASCADE"),nullable=True,index=True
    )
    title:Mapped[str] = mapped_column(String(128),default="新对话",nullable=False)

    #会话上下文压缩，存储会话内的浓缩摘要
    context_summary:Mapped[str|None] = mapped_column(Text,nullable=True)
    compressed_until: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at:Mapped[datetime] = mapped_column(
        DateTime,server_default=func.now(),nullable=False
    )
    updated_at:Mapped[datetime] = mapped_column(
        DateTime,server_default=func.now(),onupdate=func.now(),nullable=False
    )
    messages:Mapped[list["Message"]] = relationship(
        back_populates="conversation",
        cascade="all,delete-orphan",
        order_by="Message.id"
    )


class Message(Base):
    """
    消息表，存储所有用户的所有历史消息
    """
    __tablename__ = "messages"

    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    conversation_id:Mapped[int] = mapped_column(
        ForeignKey("conversations.id",ondelete="CASCADE"),nullable=False,index=True
    )

    role:Mapped[str] = mapped_column(String(16),nullable=False)
    content:Mapped[str] = mapped_column(Text,nullable=False)

    citations:Mapped[str|None] = mapped_column(Text,nullable=True)
    token_count:Mapped[int|None] =mapped_column(Integer,nullable=True)

    created_at:Mapped[datetime] = mapped_column(
        DateTime,server_default=func.now(),nullable=False
    )
    conversation:Mapped["Conversation"] = relationship(
        back_populates="messages"
    )








