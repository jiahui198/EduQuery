"""
本模块用于设计对我们爬取到的网页数据进行清洗
    正文清洗：去掉网页抓取的噪声、空行、空白等
"""
import re

def _flex(phrase:str)->str:
    """
    把短语转成「字符间允许任意空白」的正则片段，防止被换行拆断。
    """
    return r"\s*".join(map(re.escape, phrase))


#正则表达式
NOISE_PATTERNS = [
    r"发布人：[\s\S]{0,60}?" + _flex("已有人浏览"),        # 发布信息（常被拆行）
    r"您的浏览器版本过低[\s\S]{0,100}?" + _flex("版本）"),  # 浏览器升级提示
    r"上一条[:：][\s\S]{0,80}",
    r"下一条[:：][\s\S]{0,80}",
    r"^来源：\s*$",                                        # 只剩「来源：」的空行
    r"^打印本页[\s\S]{0,20}$",
]


def clean_text(text: str) -> str:
    """
    清洗网页提取出的正文。

    :param text: fetch_article 提取出来的原始正文
    :return: 清洗后的纯文本
    """
    if not text:
        return ""

    for p in NOISE_PATTERNS:
        text = re.sub(p, "", text, flags=re.M)

    lines = []
    for line in text.split("\n"):
        line = re.sub(r"\s+", " ", line).strip()
        if len(line) < 2:
            continue
        lines.append(line)

    result = []
    for line in lines:
        if not result or result[-1] != line:
            result.append(line)

    return "\n".join(result)