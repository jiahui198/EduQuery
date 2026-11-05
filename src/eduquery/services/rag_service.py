"""
本模块用于设计rag问答的主流程：检索->拼接上下文->交给大模型->携带引用来源返回
"""
import json
from collections.abc import AsyncIterator

from loguru import logger

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate,MessagesPlaceholder#可变插槽模版
from eduquery.schemas.chat import AskResponse, SourceItem
from eduquery.core.llm import get_chat_model
from eduquery.core.exceptions import LLMError
from sqlalchemy.ext.asyncio import AsyncSession
from eduquery.services import (
    history_service,
    conversation_service,
    router_service,
    retrieval_service
)
from eduquery.core.db import async_session_maker


#系统提示词，适用于需要查询校园知识库的情况
SYSTEM_PROMPT = """
你是高校知识库问答系统，只依据【参考资料】回答。
规则：
1.只能用参考资料里的内容作答，资料里没有就说"知识库里没有参考信息"，不允许编造
2.引用到的地方在句末尾[1][2]，编号必须与资料编号一致
3.回答用中文，简洁分段
"""

#通用提示词，适用于不需要查询知识库的通用情况
GENERAL_PROMPT = ("你是高校知识库问答助手。当前问题不需要查询校内知识库，"
                  "请用你的通用已有知识回答，中文、简洁。不要编造学校的具体规定")


def build_prompt()->ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system",SYSTEM_PROMPT),
            MessagesPlaceholder("history"),     #新增可变插槽模版
            ("human","【参考资料】\n{context}\n\n【用户问题】\n{question}")
        ]
    )


def build_general_prompt()->ChatPromptTemplate:
    """
    定义寒暄提示词
    """
    return ChatPromptTemplate.from_messages(
        [
            ("system",GENERAL_PROMPT),
            MessagesPlaceholder("history"),
            ("human","{question}")
        ]
    )


async def answer(question:str,db:AsyncSession,conversation_id:int,
                 student_id:int,top_k:int=5)->AskResponse:
    """
    重新定义问答函数

    :param question: 用户问题
    :param db: 数据库连接session
    :param conversation_id: 会话id
    :param student_id: 学生id
    :param top_k:返回结果数量
    :return:AskResponse
    """
    #1.读取历史最近摘要和会话内最近前12条消息
    history = await history_service.load_history(db,conversation_id)
    #2.将用户提问消息落库
    await conversation_service.append_message(
        db=db,
        conversation_id=conversation_id,
        student_id=student_id,
        role="user",
        content=question,
        citations=[]
    )
    #3.路由：将用户提问进行路由，判断是否需要向量数据库
    route = await router_service.route_question(question=question)
    #4.1判断不需要调用向量数据库:回答->落库->判断是否需要摘要
    if not route.need_rag:
        chain = build_general_prompt() | get_chat_model(temperature=0.3) | StrOutputParser()
        try:
            reply = (await chain.ainvoke({"question":question,"history":history})).strip()
        except Exception as exc:
            logger.exception("调用大模型失败")
            raise LLMError() from exc
        await conversation_service.append_message(
            db=db,
            conversation_id=conversation_id,
            student_id=student_id,
            role="assistant",
            citations=[],
            content=reply
        )
        await history_service.maybe_compress(db,conversation_id)
        return AskResponse(
            question=question,
            answer=reply,
            conversation_id=conversation_id
        )

    #4.2判断需要检索逻辑
    hits = retrieval_service.hybrid_retriever(question=question,top_k=top_k)
    if not hits:
        reply = "抱歉，知识库里没有相关文档"
        await conversation_service.append_message(
            db=db,
            conversation_id=conversation_id,
            student_id=student_id,
            role="assistant",
            content=reply,
            citations=[],
        )
        await history_service.maybe_compress(db,conversation_id)
        return AskResponse(
            question=question,
            conversation_id=conversation_id,
        )
    try:
        context,sources = retrieval_service.build_context(hits=hits)
        chain = build_prompt() | get_chat_model | StrOutputParser()
        reply = (await chain.ainvoke({"context":context,"question":question})).strip()
    except Exception as exc:
        logger.exception("调用大模型失败")
        raise LLMError() from exc
    #处理文档元数据
    source_items = [SourceItem(**s) for s in sources]
    await conversation_service.append_message(
        db, conversation_id, student_id, "assistant", reply,
        citations=[s.model_dump() for s in source_items]
    )
    await history_service.maybe_compress(db,conversation_id)
    return AskResponse(
        question=question,
        answer=reply,
        sources=source_items,
        conversation_id=conversation_id
    )



"""
以下模块用于设计FastAPI中的流式输出接口
"""
def _sse(event:str,data:dict)->str:
    """
    定义流式输出推送给前段的格式（末尾必须是两个换行符\n\n）
    :param event:事件
    :param data:推送的字典形式数据
    """
    return f"event:{event}\ndata:{json.dumps(data,ensure_ascii=False)}\n\n"


async def stream_answer(question:str,conversation_id:int,student_id:int,
                        top_k:int=5)->AsyncIterator[str]:
    """
    用于设计SSE的流式输出
    :param question: 用户问题question
    :param conversation_id: 会话id
    :param student_id:学生id
    :param top_k :返回结果数量
    :return:AsyncIterator
    """
    async with async_session_maker as db:
        history = await history_service.load_history(db,conversation_id)
        await conversation_service.append_message(
            db=db,
            conversation_id=conversation_id,
            student_id=student_id,
            role="user",
            content=question,
            citations=[]
        )
        yield _sse("meta",{"conversation_id":conversation_id})

        #1.路由判断，需不需要进行检索逻辑
        route = await router_service.route_question(question=question)
        #2.不需要路由检索直接让模型输出的情况
        if not route.need_rag:
            yield _sse("sources",{"sources":[]})
            chain = build_general_prompt() | get_chat_model(temperature=0.3) | StrOutputParser()
            parts:list[str] = []
            try:
                async for chunk in chain.astream({"question":question,"history":history}):
                    if chunk:
                        parts.append(chunk)
                        yield _sse("answer",{"text":chunk})
            except Exception:
                logger.exception("同用流式回答生成失败")
                yield _sse("error",{"code":"LLM_ERROR","message":"AI服务暂时不可用，请稍后再试"})
            reply = "".join(parts).strip()
            if reply:
                await conversation_service.append_message(
                    db=db,
                    conversation_id=conversation_id,
                    student_id=student_id,
                    role="assistant",
                    content=reply,
                    citations=[]
                )
                await history_service.maybe_compress(db,conversation_id)
            yield _sse("done",{})
            return


        #3.路由判断之后，需要检索的情况
        hits = await retrieval_service.hybrid_retriever(question=question,top_k=top_k)
        if not hits:
            reply = "抱歉，知识库里没有相关资料"
            yield _sse("answer",{"text":reply})
            await conversation_service.append_message(
                db=db,
                conversation_id=conversation_id,
                student_id=student_id,
                role="assistant",
                content=reply,
                citations=[]
            )
            await history_service.maybe_compress(db=db,conversation_id=conversation_id)
            yield _sse("done",{})
            return
        if hits:
            context,sources = retrieval_service.build_context(hits)
            source_items = [SourceItem(**s) for s in sources]
            yield _sse("sources", {"sources": [s.model_dump() for s in source_items]})

            chain = build_prompt() | get_chat_model(temperature=0.1) | StrOutputParser()
            parts =[]
            try:
                async for chunk in chain.astream(
                        {"context": context, "question": question, "history": history}
                ):
                    if chunk:
                        parts.append(chunk)
                        yield _sse("answer",{"text":chunk})
            except Exception:
                logger.exception("流式生成失败")
                yield _sse("error",{"code":"LLM_ERROR","message":"AI服务暂时不可用，请稍后再试"})
            reply = "".join(parts).strip()
            if reply:
                await conversation_service.append_message(
                    db,conversation_id,student_id,"assistant",reply,
                citations = [s.model_dump() for s in source_items])
                await history_service.maybe_compress(db, conversation_id)
                yield _sse("done", {})












