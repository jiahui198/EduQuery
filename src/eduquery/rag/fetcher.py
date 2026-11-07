"""
本模块用于设计我们对官网上面的内容进行爬取并返回dict:
    官网抓取：栏目列表页->文章链接->正文HTML
"""
import asyncio
import re
#httpx网络请求库，现代http请求流行库，包含requests同步请求和aiohttp异步请求
import httpx

#拼接url，把绝对路径和基础域名拼成完整的url
from urllib.parse import urljoin
from bs4 import BeautifulSoup


HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}    #爬取请求头
ARTICLE_RE = re.compile(r"/info/\d+/\d+\.html?$")     #正则表达式，匹配网站上面的info连接


async def _get(client:httpx.AsyncClient,url:str)->str:
    """
    定义网络请求函数，异步进行网络请求，返回网络请求之后得到的html文本
    :param client: 异步网络连接
    :param url: 请求url地址
    :return: 网页文本数据
    """
    r = await client.get(url,headers=HEADERS,follow_redirects=True,timeout=20.0)
    r.raise_for_status()
    r.encoding = r.encoding or "utf-8"
    return r.text


async def list_article_urls(list_url:str,limit:int=20)->list[str]:
    """
    请求出栏目列表中的内容，使用re块过滤出带有info文本的连接地址
    :param list_url:网站url
    :param limit:抓取数量
    :return:info文本地址列表
    """
    async with httpx.AsyncClient() as client:
        html = await _get(client,list_url)

    #使用beautiful解析请求出来的数据
    soup = BeautifulSoup(html,"lxml")

    urls = []
    for a in soup.find_all("a",href=True):
        # 将提取到的相对路径链接与网页本身url进行拼接形成绝对路径
        href = urljoin(list_url,a["href"])
        if ARTICLE_RE.search(href) and href not in urls:
            urls.append(href)
    return urls[:limit]


async def fetch_article(url:str)->dict:
    """
    抓单单篇文章，返回标题与正文文本
    :param url: list_article_urls 获得的info链接
    :return: 标题与文本
    """
    async with httpx.AsyncClient() as client:
        html = await _get(client,url)
    soup = BeautifulSoup(html,"lxml")

    title = (soup.title.get_text(strip=True) if soup.title else "").split("-")[0]
    node = soup.select_one("div.n_nry_main") or soup.select_one("div.n_nry")
    text = node.get_text("\n", strip=True) if node else ""
    return {"title": title, "url": url, "raw_text": text}





