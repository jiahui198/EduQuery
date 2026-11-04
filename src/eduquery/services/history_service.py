"""
本模块用于设计摘要功能，判断消息条数是否到达总结摘要的条件，
到达则利用大模型生成摘要。
"""
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from eduquery.models.conversation import Conversation,Message
from sqlalchemy import select, func
from eduquery.services import conversation_service
from eduquery.core.config import settings
from langchain_core.prompts import ChatPromptTemplate
from eduquery.core.llm import get_chat_model
from langchain_core.output_parsers import StrOutputParser


SUMMARY_PROMPT = """你是高校问答系统的对话摘要助手。
把【已有摘要】和本轮【更早对话】合并成一段不超过200字的中文摘要。
只保留事实：学生问过什么、答过什么、涉及哪些政策/时间/金额/流程。
不要客套话，不要编号，不要加入资料里没有的内容。

【已有摘要】
{old_summary}"""


async def load_history(db:AsyncSession,conversation_id:int)->list[dict]:
    """
    将最近12条的历史对话和会话中生成的摘要拼接在一起，用于最终喂给模型
    :param db:数据库连接session
    :param conversation_id:会话id
    :return:
    """
    history:list[dict] = []

    conv = await db.get(Conversation,conversation_id)
    if conv is None:
        return []

    #取最近的12条消息数据
    msgs = await conversation_service.window_message(
        db=db,
        conversation_id=conversation_id,
        limit = settings.HISTORY_TURNS*2,
        after_id=conv.compressed_until or 0
    )
    if conv.context_summary:
        history.append({"role":"system","content":f"更早对话的摘要{conv.context_summary}"})
    history +=[{"role":m.role,"content":m.content} for m in msgs]
    return history


async def count_uncompressed(db:AsyncSession,conversation_id:int,after_id:int)->int:
    """
    设计用于统计还有多少条未被压缩的消息条数，id>compressed_until(after_id)
    :param conversation_id:会话id
    :return: 为处理消息条数
    """
    return (await db.execute(
        select(func.count()).select_from(Message)
        .where(Message.conversation_id == conversation_id, Message.id > after_id)
    )).scalar() or 0


async def maybe_compress(db:AsyncSession,conversation_id:int)->None:
    """
    判断当未进行压缩摘要的消息条数大于我们config里面设置的消息阈值就出发摘要；
    把「除最近 HISTORY_TURNS*2 条以外」的老消息喂给模型生成摘要，
    :return:
    """
    conv = await db.get(Conversation,conversation_id)
    if conv is None:
        return

    after = conv.compressed_until or 0

    #判断未压缩摘要条数是否小于触发摘要阈值
    if await count_uncompressed(db=db,conversation_id=conversation_id,after_id=after)<=settings.COMPRESS_TRIGGER:
        return

    #取出所有未被摘要压缩的消息列表,消息列表按照升序排序
    stmt = select(Message).where(Message.conversation_id==conversation_id,Message.id>after).order_by(Message.id.asc())
    rows = (await db.execute(stmt)).scalars().all()

    keep = settings.HISTORY_TURNS*2
    to_compress = rows[:len(rows)-keep]
    if not to_compress:
        return

    dialogue = "\n".join(f"{m.role}:{m.content} "for m in to_compress)

    chain = (
        ChatPromptTemplate.from_messages(
            [
                ("system",SUMMARY_PROMPT),
                ("human","【更早对话】{dialogue}")
            ]
        ) | get_chat_model(temperature=0.0)
          | StrOutputParser()
    )
    try:
        summary = (await chain.ainvoke(
            {"old_summary":conv.context_summary,"dialogue":dialogue}
        )).strip()
    except Exception as exc:
        logger.exception("会话 {} 上下文压缩失败，本次跳过", conversation_id)
        return
    #最后落如我们的Conversation表的summary字段中
    await conversation_service.append_context_summary(db=db,conversation_id=conversation_id,summary=summary,compressed_until=to_compress[-1].id)








