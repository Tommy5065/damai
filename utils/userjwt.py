import jwt
import datetime
import os
from utils.log import logger


async def generateToken(useranme: str, userid: int):
    expire_time_object = datetime.datetime.now() + datetime.timedelta(weeks=1)
    exp = int(expire_time_object.timestamp())
    payload = {"username": useranme, "userid": userid, "exp": exp}
    token = jwt.encode(payload, os.getenv("SECRET_KEY"), os.getenv("ALGORITHM"))

    if isinstance(token, bytes):  # 转换token编码
        token = token.decode("utf-8")
        return token
    return token


async def validToken(token: str) -> str:
    try:
        token_data = jwt.decode(token, os.getenv("SECRET_KEY"), os.getenv("ALGORITHM"))
        if token_data:
            userID = token_data.get("userid")
            if userID is None:
                raise ValueError("无效用户")
            return userID
    except Exception as e:
        logger.error(e)
        raise ValueError("无效凭证")
