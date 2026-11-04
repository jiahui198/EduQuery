"""
本模块用于设计数据结构：
使用pydantic框架来定义数据模型，规定fastapi接口的出参和入参;
本chat模块用于设计问答接口的出参和入参数据模型
"""
from pydantic import BaseModel,Field

class AskRequest(BaseModel):
    """
    用户问题的入参
    """
    question:str = Field(min_length=1,max_length=1000,description="用户问题")
    conversation_id:int|None = Field(default=None,description="会话id，不传则自动新建会话")

class SourceItem(BaseModel):
    """
    定义一个文档内容引用来源数据类型
    """
    index:int
    title:str
    source_url:str|None = None
    score:float


class AskResponse(BaseModel):
    question:str
    answer:str
    sources:list[SourceItem]=[]
    conversation_id:int


class RouteResult(BaseModel):
    """
    路由判断模型
    """
    need_rag:bool = Field(description="是否需要查询学校知识库才能回答")
    reason:str = Field(description="说明判断依据")
