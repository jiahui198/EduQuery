"""
本模块用于设计程序的异常兜底机制
    业务代码只需要raise异常，不用try-except
    add_exception_handler(异常类，处理函数)：当抛出此异常时交给handler函数进行处理
"""
from typing import Any
from fastapi import FastAPI,status,Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from loguru import logger
from eduquery.core.config import settings

"""
本阶段定义所有可能遇到的异常情况
"""
class BizException(Exception):
    """
    定义所有业务异常基类
    """
    code = "BIZ_ERROR"
    http_status = status.HTTP_400_BAD_REQUEST
    message = "请求处理失败"

    def __init__(self,message:str|None=None,detail:Any=None):
        self.message = message or self.message
        self.detail = detail
        # 执行父类Exception类的init方法，使用实例属性self.message为父类赋值
        super().__init__(self.message)


class AuthError(BizException):
    """
    登录鉴权异常：没登录/token造假->401
    """
    code = "AUTH_FAILED"
    http_status = status.HTTP_401_UNAUTHORIZED
    message = "请先登录"


class TokenExpiredError(AuthError):
    """
    登录token过期异常兜底->401
    """
    code = "TOKEN_EXPIRED"
    message = "登录已过期，请重新登录"


class PermissionDeniedError(BizException):
    """
    登录权限错误异常兜底->403
    """
    code = "PERMISSION_DENIED"
    http_status = status.HTTP_403_FORBIDDEN
    message = "你没有权限做这件事"


class NotFoundError(BizException):
    """
    查不到东西->404
    """
    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND
    message = "没有查询的相关知识库"

    def __init__(self,resource:str="内容",detail:Any=None):
        super().__init__(message=f"{resource}不存在",detail=detail)


class ConflictError(BizException):
    """
    资源冲突，比如学号用户名重复
    """
    code = "CONFLICT"
    http_status = status.HTTP_409_CONFLICT
    message="资源冲突"


class LLMError(BizException):
    """
    调用阿里百炼模型失败->502
    """
    code="LLM_ERROR"
    http_status = status.HTTP_502_BAD_GATEWAY
    message = "AI服务暂时不可用"


"""
本阶段用于设计程序的异常处理函数，捕获抛出的异常->转成统一格式的json返回给前段
"""
def _resp(status_code:int,code:str,message:str,detail:Any=None)->JSONResponse:
    """
    异常处理响应结构化返回json结构数据
    """
    headers = {"WWW-Authenticate":"Bearer"} if status_code==401 else None
    return JSONResponse(

        status_code=status_code,
        content={"code":code,"message":message,"detail":detail},
        headers=headers
    )

#自定义handler
async def biz_handler(request:Request,exc:BizException)->JSONResponse:
    """
    处理biz基类异常
    """
    return _resp(status_code=exc.http_status,message=exc.message,code=exc.code,detail=exc.detail)


async def http_handler(request:Request,exc:StarletteHTTPException)->JSONResponse:
    """
    http异常捕获
    """
    return _resp(status_code=exc.status_code,code="HTTP_ERROR",message=str(exc.detail),detail=str(exc.detail))


async def catch_all_handler(request:Request,exc:Exception)->JSONResponse:
    """
    兜底异常机制
    """
    logger.exception("服务器内部错误“{}",exc)
    message = str(exc) if settings.DEBUG else "服务器开小差了，请稍后再试"
    return _resp(500, "INTERNAL_ERROR", message)


def register_exception_handlers(app:FastAPI)->None:
    """
    注册所有错误异常
    """
    app.add_exception_handler(BizException,biz_handler)             #如果抛出BizException->交给biz_handler
    app.add_exception_handler(StarletteHTTPException,http_handler)  #如果抛出StarletteHTTPException->交给http_handler
    app.add_exception_handler(Exception,catch_all_handler)          #所有的异常兜底





