"""
本模块用于设计长期记忆表，通过模型总结存储用户的兴趣爱好等内容
"""
from datetime import datetime

from sqlalchemy import DateTime,ForeignKey,Integer,String,Text,func
from sqlalchemy.orm import Mapped,mapped_column

from eduquery.models.base import Base


class StudentMemory(Base):
    """
    长期记忆表，用于存储学生的事实数据等
    """
    __tablename__ = "student_memories"

    id:Mapped[int] = mapped_column(Integer,primary_key=True,autoincrement=True)
    student_id:Mapped[int] = mapped_column(
        ForeignKey("students.id",ondelete="CASCADE"),nullable=False,index=True
    )

    content:Mapped[str] = mapped_column(Text,nullable=False)                #事实数据
    category:Mapped[str|None] = mapped_column(String(32),nullable=True)     #分类：学业、偏好、习惯

    source_conversation_id:Mapped[int|None] = mapped_column(                #ondelete 将其置空，不该把长期记忆内容一并删掉
        ForeignKey("conversations.id",ondelete="SET NULL"),nullable=True
    )

    created_at:Mapped[datetime] = mapped_column(DateTime,server_default=func.now(),nullable=False)
    updated_at:Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
