"""
本模块用于设计对密码进行哈希和校验密码的功能；
同时设计jwt鉴权，签发token
"""

from datetime import datetime,timedelta,timezone

from jose import JWTError,jwt
from passlib.context import CryptContext
from eduquery.core.config import settings
#分别导入两个异常，登录鉴权失败异常、token过期异常
from eduquery.core.exceptions import AuthError,TokenExpiredError


pwd_context = CryptContext(schemes=["bcrypt"],deprecated="auto")

def hash_password(plain:str)->str:
    """
    明文密码进行哈希，将用户传的明文密码进行哈希
    :param plain:明文密码
    :return:hash密码
    """
    return pwd_context.hash(plain)


def verify_password(plain:str,hashed:str)->bool:
    """
    校验明文密码与哈希密码
    :param plain: 用户传入的明文密码
    :param hashed: 哈希密码
    :return: bool
    """
    return pwd_context.verify(plain,hashed)


def create_access_token(user_id:int,role:str)->str:
    """
    签发jwt
    :param user_id:用户id
    :param role: 角色身份
    :return: jwt token
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload={
        "sub":str(user_id),
        "role":role,
        "exp":expire
    }
    return jwt.encode(payload,settings.JWT_SECRET,algorithm=settings.JWT_ALGORITHM)


def decode_token(token:str)->dict:
    """
    将用户发过来的token进行解码鉴权

    :param token: token
    :return: {"user_id":int,"role":str}
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM]
        )
    #jwt失效过期异常
    except jwt.ExpiredSignatureError:
        raise TokenExpiredError
    #jwt错误异常
    except JWTError:
        raise AuthError()

    try:
        user_id = int(payload.get("sub"))
    except (TypeError,ValueError):
        raise AuthError()

    role = payload.get("role")
    if role not in ("student","admin"):
        raise AuthError()

    return {"user_id":user_id,"role":role}




