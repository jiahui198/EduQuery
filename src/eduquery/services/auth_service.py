"""
本模块用于设计用户登录鉴权的逻辑处理:
    注册、登录、签发token
"""
from eduquery.models.user import  User,Admin
from eduquery.core.exceptions import ConflictError,PermissionDeniedError,AuthError
from eduquery.schemas.auth import StudentRegister,StudentLogin,AdminLogin
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from eduquery.core.security import hash_password,verify_password,create_access_token


class StudentNoExistsError(ConflictError):
    """
    学号已注册
    """
    code = "STUDENT_NO_EXISTS"
    message = "该学号已注册"

async def register_student(data:StudentRegister,db:AsyncSession)->User:
    """
    定义用户注册逻辑
    :param data:用户学生发送的数据模型
    :param db:数据库连接session
    :return:user
    """
    hit = (await db.execute(
        select(User.id).where(User.student_no==data.student_no)
    )).scalar_one_or_none()
    if hit is not None:
        raise StudentNoExistsError(detail=data.student_no)

    user = User(
        student_no=data.student_no,
        hashed_password=hash_password(data.password),   #将发送过来的明文密码进行哈希
        nickname=data.nickname,
        major=data.major,
        is_active=True
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def login_student(data:StudentLogin,db:AsyncSession)->str:
    """
    定义学生的学生登录逻辑,登录成功后，将为用户学生签发token
    :param data: 用户登录传送的数据
    :param db: 数据库连接session
    """
    user = (await db.execute(select(User).where(User.student_no==data.student_no))).scalar_one_or_none()

    #校验账号和密码
    if user is None or not verify_password(data.password,user.hashed_password):
        raise AuthError("账号或密码错误")

    if not user.is_active:
        raise PermissionDeniedError("账号已被封禁")

    return create_access_token(user_id=user.id,role="student")


async def login_admin(data:AdminLogin,db:AsyncSession)->str:
    """
    定义管理员登录的鉴权逻辑
    :param data: 管理员登录传送的账号密码
    :param db: 数据库连接session
    :return: token
    """
    admin = (await db.execute(
        select(Admin).where(Admin.username==data.username)
    )).scalar_one_or_none()

    if admin is None or not verify_password(data.password,admin.hashed_password):
        raise AuthError("用户名或密码错误")

    if not admin.is_active:
        raise PermissionDeniedError("账号已被封禁")

    return create_access_token(admin.id,role="admin")









