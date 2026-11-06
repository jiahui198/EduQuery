"""
本模块用于设计跨会话的长期记忆：
    每轮回答后从对话中提取关于学生本人的持久事实，存入student_memories
    回答前把已有记忆注入system prompt
"""
import json

from loguru import logger

from eduquery.core.llm import get_chat_model
from eduquery.models.memory import StudentMemory
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from eduquery.core.config import settings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from eduquery.schemas.memory import MemoryExtractResult
from langchain_core.messages import SystemMessage,HumanMessage


EXTRACT_PROMPT ="""
你是学生个人信息提取助手。
下面的【已有记忆】是该学生已经被记录的持久事实。
用户会发来他刚问的一句话，请只从这句话里找出"关于学生本人的新的持久事实"。

规则：
1.只提取学生自述的信息：专业、年级、学院、兴趣、目标、习惯、偏好等
2.学校的规定、比赛信息这类公共内容不算
3.提问里没有提到自己的信息，facts 返回空列表
4.已有记忆里意思相同的事实不要重复提取
5.对已有事实的更正算新事实，按纠正后的说法输出
6.每条事实一句话说清，不要编造、不要推测

【已有记忆】
{existing}
"""

async def load_memories(db:AsyncSession,student_id:int,
                        limit:int|None=None)->list[StudentMemory]:
    """
    读取学生的长期记忆
    """
    stmt = (
        select(StudentMemory)
        .where(StudentMemory.student_id==student_id)
        #查询最近的以及由最近到最早时间
        .order_by(StudentMemory.updated_at.desc(),StudentMemory.id.desc())
        .limit(limit or settings.MEMORY_MAX_ITEMS)
    )
    return list((await db.execute(stmt)).scalars().all())


async def format_memory_block(memories:list[StudentMemory])->str:
    """
    拼接长期记忆
    """
    if not memories:
        return ""
    lines = [f"{m.content}" for m in memories]
    return "【该学生的长期记忆】\n"+"\n".join(lines)


async def extract_memories(db:AsyncSession,student_id:int,
                           conversation_id:int,question:str)->int:
    """
    提取以往记忆，并结合本轮问答，重新让模型生成结构化记忆信息，并添加到数据库中
    :param db:数据库连接session
    :param student_id:学生id
    :param conversation_id:会话id
    :param question:用户问题
    :return:最终返回生成的记忆条数
    """
    if not question.strip():
        return 0

    existing = await load_memories(
        db=db,
        student_id=student_id,
        limit=settings.MEMORY_RECENT_FOR_DEDUP
    )
    existing_text = "\n".join(f"{m.content}" for m in existing) or "暂无"

    try:
        llm = get_chat_model(temperature=0.0).with_structured_output(MemoryExtractResult)

        result = await llm.ainvoke(
            [SystemMessage(EXTRACT_PROMPT.format(existing=existing_text)),
             HumanMessage(question[:500])
             ]
        )
    except Exception:
        logger.exception("学生{}长期记忆提取失败，跳过本次提取对话",student_id)
        return 0
    if result is None:
        return 0

    facts = [f for f in result.facts if f.content.strip()][:5]
    for f in facts:
        db.add(StudentMemory(
            student_id=student_id,
            content=f.content.strip(),
            category=f.category,
            source_conversation_id=conversation_id
        ))
    if facts:
        await db.commit()
        logger.info("学生{}本轮长期记忆{}条",student_id,len(facts))

    return len(facts)








