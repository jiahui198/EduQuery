"""
本模块用于设计rag问答的主流程：检索->拼接上下文->交给大模型->携带引用来源返回
"""
from loguru import logger

from langchain_core.messages import SystemMessage,HumanMessage

from eduquery.schemas.chat import AskResponse, SourceItem
from eduquery.services.retrieval_service import retriever,build_context
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
    用于设计rag回答问题的主函数

    :param question: 用户输入的问题
    :param top_k:检索文档数量默认为前五个
    :return:
    """
    #返回检索到的结果列表
    hits = await retriever(question=question,top_k=top_k)

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













