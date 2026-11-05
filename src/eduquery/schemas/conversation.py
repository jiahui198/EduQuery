"""
本模块用于设计会话接口，会话接口的出参入参，用于展示会话侧边栏
"""
import json
from pydantic import BaseModel,ConfigDict,Field,field_validator
from datetime import datetime

class ConversationCreate(BaseModel):
    """
    新建会话的入参
    """
    title:str|None = Field(default=None,max_length=128)


class MessageOut(BaseModel):
    """
    消息的出参
    """
    model_config = ConfigDict(from_attributes=True)

    id:int
    role:str
    content:str
    citations:list[dict]=[]
    token_count:int|None=None
    created_at:datetime

    @field_validator("citations",mode="before")
    @classmethod
    def _parse_citations(cls, v):
        """citations 存的是 JSON 文本，读出来转回列表；解析失败就给空列表兜底"""
        if v in (None, "", []):
            return []
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (ValueError, TypeError):
                return []
        return v


class ConversationOut(BaseModel):
    """
    会话的基本信息
    """
    model_config = ConfigDict(from_attributes=True)

    id:int
    title:str
    created_at:datetime
    updated_at:datetime


class ConversationDetail(ConversationOut):
    """
    会话的详情信息：基本信息+列表信息
    """
    messages:list[MessageOut]=[]






