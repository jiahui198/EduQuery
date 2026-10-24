"""
新建学生表
"""
from datetime import datetime
from sqlalchemy import Boolean,DateTime,Integer,String,func
from sqlalchemy.orm import Mapped,mapped_column

from eduquery.models.base import Base

class User(Base):
    """
    新建学生表
    """
    __tablename__ = "students"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)

    #学生学号字段，添加索引，方便后续查询
    student_no:Mapped[str]=mapped_column(String(32),unique=True,index=True,nullable=False)
    hashed_password:Mapped[str]=mapped_column(String(256),nullable=False)
    nickname:Mapped[str|None]=mapped_column(String(64),nullable=True)
    major:Mapped[str|None]=mapped_column(String(64),nullable=True)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)

    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),onupdate=func.now(),nullable=False)

class Admin(Base):
    """
    新建管理员表
    """
    __tablename__="admins"
    id:Mapped[int]=mapped_column(Integer,primary_key=True,autoincrement=True)

    username:Mapped[str]=mapped_column(String(64),unique=True,index=True,nullable=False)
    hashed_password:Mapped[str]=mapped_column(String(256),nullable=False)
    is_active:Mapped[bool]=mapped_column(Boolean,default=True,nullable=False)

    created_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),nullable=False)
    updated_at:Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),onupdate=func.now(),nullable=False)










