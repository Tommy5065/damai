from fastapi import FastAPI, HTTPException, status, Depends, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer, OAuth2PasswordRequestForm
from typing import Optional
from pydantic import EmailStr
from passlib.hash import pbkdf2_sha256
from threading import Timer
import redis
from config.util import generateToken, validToken, logger
from .schema import Register, Token, MessageOut, CheckInfoOut
from config.data_base import registerMysqlUserSendEmail
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


async def get_mq():
    """rabbitmq对象"""
    mq = user_service.state.rabbit
    if not mq:
        raise HTTPException(status_code=500, detail="Rabbit客户端未初始化")
    yield mq.conn


def secondDeleteRedis(userID):
    r = redis.Redis(host="localhost", port=6379, db=0, password=123456)
    logger.info("第二次删除redis")
    r.delete(f"userservice:{userID}")
    r.close()


@user_service.post("/register", response_model=MessageOut)
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
        return MessageOut(message="注册成功")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="register fail."
    )


@user_service.post("/login", response_model=Token, tags=["user"])
async def login(loginData: OAuth2PasswordRequestForm = Depends(), db=Depends(get_db)):
    """用户登录"""
    # 异步连接数据库，查询密码是否正确，用户名是否存在等
    mysqlPasswordAndUserID = await db.getMysqlUser(
        connObject=db,
        sql=("select password,user_id from usertable where user_name=%s"),
        param=(loginData.username),
    )

    if not mysqlPasswordAndUserID:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    mysql_password, user_id = mysqlPasswordAndUserID[0][0], mysqlPasswordAndUserID[0][1]
    if pbkdf2_sha256.verify(
        loginData.password, hash=mysql_password
    ):  # 登录成功给个OAuth
        access_token = await generateToken(loginData.username, user_id)
        return {"token": access_token}

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="用户名或密码错误",
        headers={"WWW-Authenticate": "Bearer"},
    )


@user_service.get("/check", tags=["user"], response_model=CheckInfoOut)
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
        return cache

    logger.warning("数据未缓存,访问数据库")
    detail_data = await db.getMysqlUser(
        connObject=db,
        sql=("select user_name,user_email,iden_id from usertable where user_id=%s"),
        param=(userID),
    )

    # 用字典推导式
    user_name, email, iden_id = detail_data[0][0], detail_data[0][1], detail_data[0][2]
    if iden_id is None:
        iden_id = "null"
    await redis.createCache(
        redis,
        f"userservice:{userID}",
        map={"username": user_name, "email": email, "idenID": iden_id},
    )
    return {"username": user_name, "email": email, "idenID": iden_id}


@user_service.patch("/update", tags=["user"], response_model=MessageOut)
async def update(
    username: Optional[str] = Form(None),
    useremail: Optional[EmailStr] = Form(None),
    idenID: Optional[str] = Form(None),
    access_token: str = Depends(token),
    db=Depends(get_db),
    redis=Depends(get_redis),
):
    """修改信息,涉及到缓存双写一致性"""

    userID = await validToken(access_token)

    # 构建更新字典
    update_data = {
        k: v
        for k, v in {
            "username": username,
            "useremail": useremail,
            "idenID": idenID,
        }.items()
        if v is not None
    }

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="没有要更新的字段"
        )

    # 验证姓名唯一性
    if "username" in update_data:
        nameExist = await db.checkMysqlUser(
            db,
            sql="select exists(select 1 from usertable where user_name=%s)",
            param=(update_data["username"]),
        )

        if nameExist[0]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="用户名已存在",
            )
    # 字典映射
    field_map = {
        "username": "user_name",
        "useremail": "user_email",
        "idenID": "iden_id",
    }
    # 动态构建set语句
    set_case = []
    params = []
    for key, val in update_data.items():
        if key in field_map:
            set_case.append(f"{field_map[key]}=%s")
            params.append(val)
    params.append(userID)
    sql = f"update usertable set {', '.join(set_case)} where user_id=%s "

    logger.info("第一次删除缓存")
    await redis.deleteCache(redis, f"userservice:{userID}")

    # 更新数据库
    updateMysqlData = await db.updateMysqlUser(db, sql, param=tuple(params))
    if not updateMysqlData:
        await db.updateMysqlUser(db, sql, param=tuple(params))

    # 再次删除缓存,延迟双删
    t = Timer(2, secondDeleteRedis, args=(userID,))
    t.start()
    return MessageOut(message="修改成功")


@user_service.patch("/update/password", tags=["user"], response_model=MessageOut)
async def updatePassword(
    currentPassword: str = Form(...),
    newPassword: str = Form(...),
    confirmNewPassword: str = Form(...),
    db=Depends(get_db),
    access_token=Depends(token),
):
    userID = await validToken(access_token)
    mysqlPassword = await db.checkMysqlUser(
        db, sql="select password from usertable where user_id=%s", param=(userID,)
    )
    mysqlPassword = mysqlPassword[0]
    if pbkdf2_sha256.verify(currentPassword, hash=mysqlPassword):
        if newPassword == confirmNewPassword:
            newPassword = pbkdf2_sha256.hash(confirmNewPassword)
            await db.updateMysqlUser(
                db,
                sql="update usertable set password=%s where user_id=%s",
                param=(newPassword, userID),
            )
            return MessageOut(message="修改密码成功")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="新密码前后不一致"
        )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="旧密码不正确")
