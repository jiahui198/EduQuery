"""
本模块用于设计用户登录鉴权的接口路由
"""
from fastapi import APIRouter,Depends,status
from sqlalchemy.ext.asyncio import AsyncSession
from eduquery.schemas .auth import (
StudentOut,
StudentRegister,
TokenResponse,
StudentLogin,
AdminLogin,
AdminOut
)
from eduquery.core.db import get_db
from eduquery.core.deps import get_current_user,get_current_admin
from eduquery.services import auth_service
from eduquery.models.user import User,Admin



router = APIRouter(prefix="/auth",tags=["auth"])

@router.post("/register",response_model=StudentOut,
             status_code=status.HTTP_201_CREATED,summary="学生注册接口")
async def register(data:StudentRegister,db:AsyncSession = Depends(get_db)):
    """
    用于设计学生用户的注册接口
    :param data: 用户注册发送的数据请求
    :param db: 数据库连接session
    :return: 结构化学生对象
    """
    user = await auth_service.register_student(data=data,db=db)
    return StudentOut.model_validate(user)


@router.post("/login",response_model=TokenResponse,summary="学生登录")
async def login(data:StudentLogin,db:AsyncSession = Depends(get_db)):
    """
    用于设计用户的登录接口
    :param data: 用户登录发送的数据请求
    :param db: 数据库连接session
    :return:jwt token
    """
    token = await auth_service.login_student(data=data,db=db)
    return TokenResponse(access_token=token)


@router.post("/admin/login",response_model=TokenResponse,summary="管理员登录")
async def admin_login(data:AdminLogin,db:AsyncSession=Depends(get_db)):
    """
    用于设计管理员登录接口
    :param data: 用户登录发送的数据请求
    :param db:数据库连接session
    :return:jwt token
    """
    token = await auth_service.login_admin(data=data,db=db)
    return TokenResponse(access_token=token)

@router.get("/me",response_model=StudentOut,summary="当前登录的学生信息")
async def me(current_user:User = Depends(get_current_user)):
    """
    用于设计返回学生的基本信息接口
    :param current_user: 学生信息类型
    :return: 结构化数据
    """
    return StudentOut.model_validate(current_user)


@router.get("/admin/me",response_model=AdminOut,summary="当前登录的管理员信息")
async def admin_me(current_user:Admin = Depends(get_current_admin)):
    """
    用于设计返回管理员的基本信息
    :param current_user: 依赖注入管理员信息
    :return: 结构化数据
    """
    return AdminOut.model_validate(current_user)








