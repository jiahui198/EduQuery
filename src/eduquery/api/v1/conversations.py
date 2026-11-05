"""
本模块用于设计会话额管理接口：
    新建会话
    列出会话列表
    会话详情
    删除会话
"""
from fastapi import APIRouter,Depends,Query
from sqlalchemy.ext.asyncio import AsyncSession

from eduquery.core.db import get_db
from eduquery.core.deps import get_current_user
from eduquery.models import User
from eduquery.schemas.conversation import (
ConversationOut,
ConversationCreate,
ConversationDetail,
MessageOut
)
from eduquery.services import (
conversation_service
)


router = APIRouter(prefix="/conversations",tags=["conversation"])

@router.post("",response_model=ConversationOut)
async def create_conversation(
        data:ConversationCreate,
        db:AsyncSession=Depends(get_db),
        current_user:User=Depends(get_current_user)
)->ConversationOut:
    """
    定义创建会话函数
    :param data: 会话创建信息ConversationCrete
    :param db: 数据库连接session
    :param current_user: 注入的用户
    :return: 会话出参信息
    """
    conv = await conversation_service.create_conversation(
        db,current_user.id,title=data.title if data else None
    )
    return ConversationOut.model_validate(conv)


@router.get("",response_model=list[ConversationOut],summary="我的会话列表")
async def list_conversations(
        limit:int=Query(default=20,ge=1,le=100,description="每页条数"),
        offset:int=Query(default=0,ge=0,description="每页跳过条数"),
        db:AsyncSession = Depends(get_db),
        current_user:User = Depends(get_current_user)
)->list[ConversationOut]:
    """
    批量获取对话列表
    :param limit:每页显示的条数
    :param offset:跳过的条数
    :param db:数据库连接session
    :param current_user:依赖注入用户基本信息
    :return:list[ConversationOut]
    """
    rows = conversation_service.list_conversation(
        db=db,
        student_id=current_user.id,
        limit=limit,
        offset=offset
    )
    return [ConversationOut.model_validate(c) for c in rows]


@router.get("/{conversation_id}",response_model=ConversationDetail,summary="获取会话详细信息")
async def get_detail_conversation(
        conversation_id:int,
        db:AsyncSession=Depends(get_db),
        user:User=Depends(get_current_user)
)->ConversationDetail:
    """
    获取会话的详细信息，包含：会话基本信息+消息列表
    """
    conv = await conversation_service.get_conversation(
        db,user.id,conversation_id
    )
    base = ConversationOut.model_validate(conv)

    msgs = await conversation_service.list_messages(db,conv.id,limit=1000)

    return ConversationDetail(
        **base.model_dump(),
        messages=[MessageOut.model_validate(m) for m in msgs],
    )


@router.get("/{conversation_id}/messages",response_model=list[MessageOut])
async def list_messages(
        conversation_id:int,
        limit: int = Query(default=50, ge=1, le=200, description="每页条数"),
        offset: int = Query(default=0, ge=0, description="跳过条数"),
        db:AsyncSession=Depends(get_db),
        user:User=Depends(get_current_user)
)->list[MessageOut]:
    """
    获取message列表
    :param conversation_id:会话id
    :param  limit:每页条数
    :param  offset:跳过条数
    :param db: 数据库连接session
    :param user:
    :return:
    """
    conv = await conversation_service.get_conversation(db,user.id,conversation_id)
    msgs = await conversation_service.list_messages(db,conv.id,limit,offset)
    return [MessageOut.model_validate(m) for m in msgs]


@router.delete("/{conversation_id}")
async def delete_conversation(
        conversation_id:int,
        db:AsyncSession=Depends(get_db),
        user:User = Depends(get_current_user),
)->None:
   """
   定义删除会话接口，并连带删除会话中消息

   :param conversation_id: 会话id
   :param db: 数据库连接session
   :param user: 依赖注入user
   """
   await conversation_service.delete_conversation(db,user.id,conversation_id)
   return None






