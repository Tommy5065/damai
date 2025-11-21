from fastapi import FastAPI, HTTPException, status, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from passlib.hash import pbkdf2_sha256
from typing import Annotated
import asyncio
from util import generateToken, validToken, logger
from .schema import Register, Login, Token
from data_base import registerMysqlUserSendEmail
from .life import life

user_service = FastAPI(title="user-service", version="1.0.0", lifespan=life)
user_service.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
token = OAuth2AuthorizationCodeBearer(
    authorizationUrl="http://localhost:8000/login",
    tokenUrl="http://localhost:8000/login",
)


async def get_db():
    """数据库连接依赖项"""
    # 从 app.state 获取连接池
    pool = user_service.state.mysql_pool
    try:
        yield pool
    finally:
        # 连接会自动归还到连接池，不需要手动关闭
        pass


async def get_redis():
    """Redis依赖项"""
    redis_client = user_service.state.redis_client
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis客户端未初始化")
    yield redis_client


@user_service.post("/register")
async def register(data: Register, tags=["user"], db=Depends(get_db)):
    """用户注册"""
    # 异步连接数据库，查询结果
    if len(data.username) > 15:
        raise ValueError("username cannot over 15 charactar.")

    name_exist = await db.getMysqlUser(
        connObject=db,
        sql=("select user_name from usertable where user_name=%s"),
        param=(data.username,),
    )
    if name_exist:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="user has exist."
        )
    # 注册成功，celery发送邮件异步任务
    password = pbkdf2_sha256.hash(data.password)
    sql = "insert into usertable(user_name,user_email,password) values(%s,%s,%s)"
    param = (
        data.username,
        data.email,
        password,
    )
    result = await registerMysqlUserSendEmail(
        connObject=db, sql=sql, param=param, email=data.email
    )
    if result:
        return {"message": "create user success."}
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="register fail."
    )


@user_service.post("/login", response_model=Token)
async def login(data: Login, tags=["user"], db=Depends(get_db)):
    """用户登录"""
    # 异步连接数据库，查询密码是否正确，用户名是否存在等
    mysql_password_id = await db.getMysqlUser(
        connObject=db,
        sql=("select password,user_id from usertable where user_name=%s"),
        param=(data.username),
    )
    mysql_password, user_id = mysql_password_id[0][0], mysql_password_id[0][1]
    if mysql_password:
        if pbkdf2_sha256.verify(
            data.password, hash=mysql_password
        ):  # 登录成功给个OAuth
            access_token = await generateToken(data.username, user_id)
            return {"token": access_token}
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="无效用户名或密码",
            headers={"WWW-Authenticate": "Bearer"},
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="用户不存在",
        headers={"WWW-Authenticate": "Bearer"},
    )


@user_service.get("/check", tags=["user"])
async def checkInfo(
    access_token: str = Depends(token),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """用户查看信息"""
    userID = await validToken(access_token)
    # 缓存命中
    logger.debug(f"{userID}号用户查询信息")
    cache = await redis.getDataRedis(redis, key=f"userservice:{userID}")
    if cache:
        return {"status": status.HTTP_200_OK, "message": "获取成功", "data": f"{cache}"}
    # 缓存未命中写入缓存

    logger.warning("数据未缓存,访问数据库")
    detail_data = await db.getMysqlUser(
        connObject=db,
        sql=("select user_name,user_email from usertable where user_id=%s"),
        param=(userID),
    )
    user_name, email = detail_data[0][0], detail_data[0][1]
    createcache = await redis.createCache(
        redis, f"userservice:{userID}", map={"username": user_name, "email": email}
    )
    return {"username": user_name, "email": email}


@user_service.post("/update", tags=["user"])
async def updateData(
    username: Annotated[str, Form()],
    useremail: Annotated[str, Form()],
    access_token: str = Depends(token),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """用户修改信息分为两种:修改密码还是修改普通信息,
    如果是修改密码,修改后要重新登录,获得新的token
    修改普通信息的话,涉及到缓存双写一致性"""

    # 1修改普通信息
    userID = await validToken(access_token)
    # 1.1 先删缓存

    await redis.deleteCache(redis, f"userservice:{userID}")

    # 更新数据库
    update_data = await db.updateMysqlUser(
        db,
        sql=("update usertable set user_name=%s,user_email=%s where user_id=%s"),
        param=(username, useremail, userID),
    )
    if not update_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="姓名重复")

    # 再次删除缓存,延迟双删
    await asyncio.sleep(100)
    await redis.deleteCache(redis, f"userservice:{userID}")
    return {"message": "更新成功并删除缓存"}
