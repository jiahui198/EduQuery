"""
本模块用于设计会话与消息的读写逻辑：
设计会话与消息的功能，主要是为了实现多轮对话的上下文压缩以及短期记忆和长期记忆。
    创建会话 create_conversation
    获得会话 get_conversation
"""
import json
from datetime import datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from eduquery.core.exceptions import NotFoundError
from eduquery.models.conversation import  Conversation,Message
from sqlalchemy import select, update, func

DEFAULT_TITLE = "新对话"
TITLE_MAX_LEN = 24


async def create_conversation(
        db:AsyncSession,
        student_id:int,
        title:str|None = None
)->Conversation:
    """
    定义根据学生的id创建新会话

    :param db:数据库连接session
    :param student_id:学生id
    :param title:标题
    """
    conv = Conversation(student_id=student_id,title=title or DEFAULT_TITLE)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def get_conversation(db:AsyncSession,student_id:int,conversation_id:int)->Conversation:
    """
    根据学生的id，获取会话

    :param db:数据库连接 session
    :param student_id:学生id
    :param conversation_id:会话id
    :return:会话对象
    """
    conv = await db.get(Conversation, conversation_id)
    if conv is None or conv.student_id != student_id:
        raise NotFoundError("会话")
    return conv


async def list_conversation(db:AsyncSession,student_id:int,
                            limit:int=20,offset:int=0)->list[Conversation]:
    """
    设计根据学生的id,从会话表中找到学生的会话列表
    :param db:数据库连接session
    :param student_id:学生id
    :param limit:分页，每页显示数量
    :param offset:跳过
    :return:会话列表
    """
    stmt = (
        select(Conversation)
        .where(Conversation.student_id==student_id)
        #按照时间降序排序，由最近的到最远的时间
        .order_by(Conversation.updated_at.desc(),Conversation.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def append_message(db:AsyncSession,conversation_id:int,student_id:int,
                         role:str,content:str,citations:list[dict],token_count:int|None=None)->Message:
    """
    设计用于将用户和模型生成消息添加到消息列表中,并更新对话表中的updated_at
    :param db: 数据库连接session
    :param conversation_id: 会话id
    :param student_id:学生id
    :param role:角色身份
    :param content:消息内容
    :param citations:消息来源出处
    :param token_count:token话费
    :return:Message
    """
    conv = get_conversation(db,student_id,conversation_id)
    if conv is None:
        raise NotFoundError("会话未找到")

    if role=="user" and conv.title ==DEFAULT_TITLE:
        conv.title = content[:TITLE_MAX_LEN] or DEFAULT_TITLE
    conv.updated_at = datetime.now()

    message = Message(
        conversation_id =conversation_id,
        role = role,
        content=content,
        citations=json.dumps(citations, ensure_ascii=False) if citations else None,
        token_count=token_count,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def list_messages(db:AsyncSession,conversation_id:int,
                        limit:int=50,offset:int=0)->list[Message]:
    """
    设计用于获得对话内的历史消息
    :param db:数据库连接session
    :param conversation_id:会话id
    :param limit:获取每页的消息条数/数量
    :param offset:分页
    :return:消息列表list[Message]
    """
    stmt = (
        select(Message)
        .where(conversation_id==conversation_id)
        #根据id从下到上升序
        .order_by(Message.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return list((await db.execute(stmt)).scalars().all())


async def window_message(db:AsyncSession,conversation_id:int,
                         limit:int = 10,after_id:int=0)->list[Message]:
    """
    取最近的limit条消息，用于生成总结,本函数用于设计取最近的十条消息
    :param db: 数据库连接session
    :param conversation_id: 会话id
    :return: list[Message]
    """
    if limit <=0:
        return []
    stmt = (
        select(Message)
        .where(Message.conversation_id==conversation_id,Message.id>after_id)
        .order_by(Message.id.desc())
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    rows.reverse()
    return rows


async def append_context_summary(db:AsyncSession,conversation_id:int,
                                 summary:int,compressed_until:int)->None:
    """
    将模型生成的总结摘要summary添加到Conversation表中
    :return:
    """
    await db.execute(
        update(Conversation)
        .where(conversation_id==conversation_id)
        .values(context_summary=summary,compressed_until=compressed_until,updated_at=func.now())
    )
    await db.commit()
    logger.info("{}会话已压缩至消息{}",conversation_id,compressed_until)


async def delete_conversation(db:AsyncSession,student_id:int,conversation_id:int):
    """
    定义根据会话id进行删除
    :param db:数据库连接session
    :param student_id:学生id
    :param conversation_id:会话id
    """
    conv = await get_conversation(db,conversation_id,student_id)
    await db.delete(conv)
    await db.commit()
    await db.refresh(conv)
    logger.info("已删除会话{}",conversation_id)






