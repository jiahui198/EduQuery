"""
本模块用于设计数据结构：
使用pydantic框架来定义数据模型，规定fastapi接口的出参和入参;
本chat模块用于设计问答接口的出参和入参数据模型
"""
from pydantic import BaseModel,Field

class AskRequest(BaseModel):
    question:str = Field(min_length=1,max_length=1000,description="用户问题")
