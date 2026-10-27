"""
本模块用于设计对密码进行哈希和校验密码的功能；
同时设计jwt鉴权，签发token
"""

from datetime import datetime,timedelta,timezone

import bcrypt
from jose import JWTError,jwt

from eduquery.core.config import settings

def hash_password(plain:str)->str:
    """
    明文密码进行哈希
    :param plain:
    :return:
    """