"""
本模块用于设计rag问答的主流程：检索->拼接上下文->交给大模型->携带引用来源返回
"""
import json
from collections.abc import AsyncIterator

from loguru import logger

from langchain_core.messages import SystemMessage,HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from eduquery.schemas.chat import AskResponse, SourceItem
from eduquery.services.retrieval_service import hybrid_retriever,build_context
from eduquery.core.llm import get_chat_model
from eduquery.core.exceptions import LLMError


SYSTEM_PROMPT = """
你是高校知识库问答系统，只依据【参考资料】回答。
规则：
1.只能用参考资料里的内容作答，资料里没有就说"知识库里没有参考信息"，不允许编造
2.引用到的地方在句末尾[1][2]，编号必须与资料编号一致
3.回答用中文，简洁分段
"""


async def answer(question:str,top_k:int=5)->AskResponse:
    """
    用于设计rag回答问题的主函数,同步函数，不能流式输出

    :param question: 用户输入的问题
    :param top_k:检索文档数量默认为前五个
    :return:
    """
    #返回检索到的结果列表（混合检索：BM25 + 向量 + RRF 融合 + rerank 精排）
    hits = await hybrid_retriever(question=question,top_k=top_k)

    if not hits:
        return AskResponse(
            question=question,
            answer="抱歉，知识库里没有相关资料"
        )

    context,sources = build_context(hits=hits)
    messages=[
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"【参考资料】\n{context}\n\n【用户问题】\n{question}")
    ]

    try:
        reply = await get_chat_model().ainvoke(messages)
    except Exception as exc:
        logger.exception("调用大模型失败")
        raise LLMError() from exc

    return AskResponse(
        question=question,
        answer = reply.content.strip(),
        sources=[SourceItem(**s) for s in sources]
    )


def build_prompt()->ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            ("system",SYSTEM_PROMPT),
            ("human","【参考资料】\n{context}\n\n【用户问题】\n{question}")
        ]
    )


def _sse(event:str,data:dict)->str:
    """
    定义流式输出推送给前段的格式（末尾必须是两个换行符\n\n）
    :param event:事件
    :param data:推送的字典形式数据
    """
    return f"event:{event}\ndata:{json.dumps(data,ensure_ascii=False)}\n\n"


async def stream_answer(question:str,top_k:int=5)->AsyncIterator[str]:
    """
    设计SSE流式输出功能
    :param question:用户问题
    :param top_k: 返回结果数量
    :return: AsyncIterator
    """
    hits = await hybrid_retriever(question=question,top_k=top_k)
    if not hits:
        yield _sse("answer",{"text":"抱歉，只是库里没有相关资料"})
        yield _sse("done",{})
        return

    context,sources = build_context(hits=hits)
    yield _sse("sources",{"sources":[SourceItem(**s) for s in sources]})

    #定义LCEL主链路
    chain = build_prompt() | get_chat_model(temperature=0.1) | StrOutputParser()
    try:
        async for chunk in chain.astream({"context":context,"question":question}):
            if chunk:
                yield _sse("answer",{"text":chunk})
    except Exception as exc:
        logger.exception("流式生成失败")
        yield _sse("error",{"code":"LLM_ERROR","message":"AI服务暂时不可用，请稍后再试"})

    yield _sse("done",{})








