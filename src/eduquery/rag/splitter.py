"""
文本切分：把一篇长文本切成重叠的小块
"""
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

#定义切分逻辑
SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=80,
    length_function=len,
    separators=["\n\n","\n","。","，"," ",""]
)

def split_text(text:str,metadata:dict)->list[Document]:
    """
    定义切分函数，将提取到的text文本进行切分得到document对象

    :param text:我们传入list[str]类型文本将返回list[Document]
    :param metadata:文本元数据
    :return:list[Document]
    """
    if not text:
        return []

    # 接收文本列表和列表元数据，将返回list[Document]
    docs = SPLITTER.create_documents(texts=[text],metadatas=[metadata])

    #为Document对象列表调价下标索引
    for i,d in enumerate(docs):
        d.metadata['chunk_index'] =i
    return docs
