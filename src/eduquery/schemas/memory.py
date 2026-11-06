"""
定义模型提取生成长期记忆是，希望模型结构化的输出
"""
from typing import Literal
from pydantic import BaseModel,Field



class MemoryFact(BaseModel):
    """
    定义模型的结构化输出，模型结构化输出长期记忆
    """
    content:str = Field(description="关于学生本人的一条持久事实")
    category:Literal["学业","偏好","目标","习惯"]|None = Field(
        default=None,description="事实分类，拿不准就留空"
    )

class MemoryExtractResult(BaseModel):
    facts:list[MemoryFact] = Field(
        default_factory=list,       #添加默认字段函数list
        description="本轮新提取到的事实，没有空事实就返回空列表"
    )
