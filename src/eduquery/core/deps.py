"""
本模块用于设计FastAPI的通用依赖：
    从请求里面携带的JWT解析出当前登录的用户；
    写法：current:User = Depends(get_current_user)
"""
from sqlalchemy import select
from eduquery.models.user import User,Admin

from fastapi.security import OAuth2PasswordBearer
from fastapi import Depends,HTTPException,status
from sqlalchemy.ext.asyncio import AsyncSession
from eduquery.core.db import  get_db
from eduquery.core.security import decode_token
from jose import JWTError
#导入token异常造价错误，登录权限拒绝error
from eduquery.core.exceptions import AuthError,PermissionDeniedError


#设置我们提取token的url，fastapi将从此url提取用户的登录token用于校验
oauth2_schema = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

async def get_current_user(
        token:str = Depends(oauth2_schema),
        db:AsyncSession = Depends(get_db)
)->User:
    """
    校验token并返回当前学生。
    用于定义设计fastapi依赖，解析校验token并返回用户id等基本信息

    :param token: FastAPI提取到的登录token
    :param db:数据库session
    :return:user用户
    """
    payload = decode_token(token)
    if payload["role"] != "student":
        raise PermissionDeniedError("只有学生身份才能访问该接口")
    stmt = select(User).where(User.id==payload["user_id"])
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise AuthError("账号不存在")
    if not user.is_active:
        raise PermissionDeniedError("账号已被封禁")
    return user

async def get_current_admin(
        token:str = Depends(oauth2_schema),
        db:AsyncSession = Depends(get_db)
)->Admin:
    """
    与上段代码功能一致，此功能是用于校验管理员token
    :return: admin用户
    """
    payload = decode_token(token)
    if payload["role"] != "admin":
        raise PermissionDeniedError("只有管理员身份才能访问该接口")
    stmt = select(Admin).where(Admin.id == payload["user_id"])
    user = (await db.execute(stmt)).scalar_one_or_none()

    if user is None:
        raise AuthError("账号不存在")
    if not user.is_active:
        raise PermissionDeniedError("账号已被封禁")
    return user



