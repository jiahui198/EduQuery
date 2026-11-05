"""
本模块将用于设计路由判断：
    即判断需不需要走rag检索流程。
    设计规则即先根据用户发送的问题中是否命中提示词，命中则走rag，没命中则不调用模型，判断不清模型介入。
"""
import re
from langchain_core.messages import SystemMessage,HumanMessage
from loguru import logger

from eduquery.schemas.chat import RouteResult
from eduquery.core.llm import get_chat_model


SMALL_TALK =re.compile(r"^(你好|您好|hi|hello|谢谢|感谢|再见|bye|你是谁|你能干什么)", re.I)
SCHOOL_HINT = ("章程", "奖学金", "处分", "报名", "通知",
               "学分", "选课", "毕业","活动","新闻","招生",
               "考试","学院","信息","公告","比赛","大赛","通知","报名","截止")


def _rule_route(question:str)->RouteResult|None:
    """
    命中规则就直接返回，没命中返回None交给LLM判断
    :param question: 用户问题
    :return:RouteResult
    """
    q = question.strip()
    if SMALL_TALK.match(q):
        return RouteResult(need_rag=False,reason = "寒暄/致谢，规则判定")
    if len(q)<=6 and not any(k in q for k in SCHOOL_HINT):
        return RouteResult(need_rag = False,reason="问题过短且无校内关键词，规则判定")
    return None



async def route_question(question:str)->RouteResult:
    """
    利用模型进行判断本次用户问题是否需要调用rag系统
    :param question: 用户问题question
    """
    #1.先使用规则进行判断
    hit = _rule_route(question=question)
    if hit:
        logger.info("路由：{}（规则）",hit.reason)
        return hit

    #2.使用LLM进行判断,LLM绑定结构化输出，LLM只能输出我们定义的字段
    llm = get_chat_model(temperature=0).with_structured_output(RouteResult)
    result = await llm.ainvoke(
        [
            SystemMessage("判断这个问题是否必须需要查询校园知识库才能回答，校园知识库中包含学校通知、公告、章程、校规等学校内容。"
                          "另外凡涉及校内发布的比赛、通知、报名安排，即使该信息在公开渠道可能存在，也必须查询校园知识库"
                          "如果需要校园知识库返回True；不需要返回False。最后并输出判断原因"),
            HumanMessage(question)
        ]
    )
    logger.info("路由：{}（LLM）",result.reason)
    return result







