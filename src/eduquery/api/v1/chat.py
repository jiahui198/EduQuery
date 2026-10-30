"""
本模块用于设计问答接口路由：接收问题->调rag_service->返回带引用来源的答案
"""
from fastapi import APIRouter
from eduquery.schemas.chat import AskRequest,AskResponse
from eduquery.services import rag_service


router = APIRouter(prefix="/chat",tags=["chat"])


@router.post("/ask",response_model=AskResponse,summary="知识库问答系统")

async def ask(data:AskRequest)->AskResponse:
    """
    用于设计基础检索问答的路由
    :param data: 用户的数据请求
    :return:返回结构化问答数据模型
    """
    return await rag_service.answer(data.question)

