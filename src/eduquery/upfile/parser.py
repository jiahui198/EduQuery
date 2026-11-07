"""
本模块用于设计管理员上传文档功能：
    将管理员上传的文档解析成纯文本
"""
from pathlib import Path
from pypdf import PdfReader
from loguru import logger
from docx import Document

SUPPORTED_EXT:set[str] = {".pdf",".docx",".txt",".md",".markdown"}


def _read_text_file(path:Path)->str:
    """
    定义读取纯文本文件函数
    :param path: 路径
    :return:str文本
    """
    raw = path.read_bytes()                         #将文件以二进制形式打开
    for enc in ("utf-8","utf-8-sig","gbk","gb18030"):#尝试解码
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8",errors="ignore")  #兜底解码逻辑


def _read_pdf(path:Path)->str:
    """
    定义读取pdf文件函数
    :param path: 路径
    :return: str文本
    """
    reader = PdfReader(str(path))       #定义reader打开pdf文件
    pages=[]
    for page in reader.pages:           #遍历pdf文件中的每一页
        t=page.extract_text() or ""     #尝试提取页面中的文字
        if t.strip():
            pages.append(t)
    return "\n".join(pages)


def _read_docx(path:Path)->str:
    """
    抽取docx的段落文字与表格内容
    :param path:文件路径
    :return:str文本
    """
    doc = Document(str(path))                                               #打开word文档
    parts=[p.text for p in doc.paragraphs if p.text.strip()]                #遍历段落提取文本内容

    for table in doc.tables:                                                #遍历文档里的所有表格
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))
    return "\n".join(parts)


def parse_file(path:str|Path)->dict:
    """
    定义解析函数，解析上传文件。判断文件格式解析
    :param path: 文件路径
    """
    p = Path(path)
    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXT:
        raise ValueError(f"不支持的文件格式“{ext}，请上传pdf/docx/txt/md")

    if ext ==".pdf":
        text = _read_pdf(p)
    elif ext == ".docx":
        text =_read_docx(p)
    else:
        text = _read_text_file(p)

    logger.info("文件解析完成：{}|{}",p.name,len(text))
    return {"title": (p.stem.strip() or p.name)[:255], "text": text}












