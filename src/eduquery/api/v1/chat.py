"""
本模块用于设计问答接口路由：接收问题->调rag_service->返回带引用来源的答案
"""
from fastapi import APIRouter
from eduquery.schemas.chat import AskRequest,AskResponse
from eduquery.services import rag_service
from fastapi.responses import StreamingResponse


router = APIRouter(prefix="/chat",tags=["chat"])


@router.post("/ask",response_model=AskResponse,summary="知识库问答系统")

async def ask(data:AskRequest)->AskResponse:
    """
    用于设计基础检索问答的路由（不含流式输出）
    :param data: 用户的数据请求
    :return:返回结构化问答数据模型
    """
    return await rag_service.answer(data.question)


@router.post("/ask/stream",summary="知识库问答系统（流式响应）")
async def ask_stream(data:AskRequest)->StreamingResponse:
    """
    定义流式检索召回精排路由
    :param data:用户请求问题数据
    """
    return StreamingResponse(
        rag_service.stream_answer(data.question),
        media_type="text/event-stream",
        headers={
            "cache-Control":"no-cache",
            "X-Accel-Buffering":"no"
        }
    )






