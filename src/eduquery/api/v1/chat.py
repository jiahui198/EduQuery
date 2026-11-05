"""
本模块用于设计问答接口路由：接收问题->调rag_service->返回带引用来源的答案
"""
from fastapi import APIRouter,Depends
from eduquery.schemas.chat import AskRequest,AskResponse
from eduquery.services import rag_service
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from eduquery.services import conversation_service
from eduquery.core.db import get_db
from eduquery.models.user import User
from eduquery.core.deps import get_current_user

router = APIRouter(prefix="/chat",tags=["chat"])


async def _resolve_conversation(db:AsyncSession,student_id:int,conversation_id:int|None):
    """
    私有定义程序内部函数：判断数据库中是否有提供的conversation_id,没有就新建
    :param db: 数据库连接session
    :param student_id: 学生id
    :param conversation_id: 会话id
    """
    if conversation_id is None:
        return await conversation_service.create_conversation(db,student_id)
    return await conversation_service.get_conversation(db,student_id,conversation_id)



@router.post("/ask",response_model=AskResponse,summary="知识库问答系统")
async def ask(data:AskRequest,
              db:AsyncSession=Depends(get_db),
              current_user:User=Depends(get_current_user))->AskResponse:
    """
    用于设计基础检索问答的路由（不含流式输出）,重新改写问答逻辑
    :param data: 用户的数据请求
    :param db :数据库连接session
    :param current_user :依赖注入的用户数据
    :return:返回结构化问答数据模型
    """
    conv = await _resolve_conversation(db,current_user.id,data.conversation_id)
    return await rag_service.answer(
        data.question,db=db,conversation_id=conv.id,student_id=current_user.id
    )



@router.post("/ask/stream",summary="知识库问答系统（流式响应）")
async def ask_stream(data:AskRequest,
                     db:AsyncSession=Depends(get_db),
                     current_user:User=Depends(get_current_user))->StreamingResponse:
    """
    定义流式检索召回精排路由，重新改写问答逻辑
    :param data:用户请求问题数据
    :param db :数据库连接session
    :param current_user :依赖注入的用户数据
    """
    conv=await _resolve_conversation(db,current_user.id,data.conversation_id)
    return StreamingResponse(
        rag_service.stream_answer(data.question,conversation_id=conv.id,student_id=current_user.id),
        media_type="text/event-stream",
        headers={
            "cache-Control":"no-cache",
            "X-Accel-Buffering":"no"
        }
    )






