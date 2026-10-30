"""
pydantic用来定义结构化的数据模型；
本模块用于设计用户登录鉴权的数据模型：
    StudentRegister 用户学生注册模型
    StudentOut   用户学生信息输出模型
"""
from pydantic import BaseModel,ConfigDict,Field

class StudentRegister(BaseModel):
    """
    学生注册入参模型
    """
    student_no:str = Field(min_length=4,max_length=32,description="学号")
    password:str = Field(min_length=6,max_length=64,description="密码")
    nickname:str|None = Field(default=None,max_length=64,description="昵称")
    major:str|None = Field(default=None,max_length=64,description="专业")


class StudentOut(BaseModel):
    """
    学生信息输出模型
    """
    model_config = ConfigDict(from_attributes=True)

    id:int
    student_no:str
    nickname:str|None
    major:str|None
    is_active:bool


class StudentLogin(BaseModel):
    """
    定义用户学生登录模型
    """
    student_no:str
    password:str


class AdminLogin(BaseModel):
    """
    定义管理员登录模型
    """
    username:str
    password:str


class AdminOut(BaseModel):
    """
    定义管理员信息出参模型
    """
    model_config = ConfigDict(from_attributes=True)

    id:int
    username:str
    is_active:bool


class TokenResponse(BaseModel):
    """
    登录成功返回的token
    """
    access_token:str
    token_type:str = "bearer"






