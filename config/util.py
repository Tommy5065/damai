from email.message import EmailMessage
import aiosmtplib
import jwt
import datetime
import logging
import sys

sender = "tommy5065@qq.com"
password = "nuojqwwktucqdfgj"
secret_key = "hcuisdhfcudshfsdcnoiyhf"
algorithm = "HS256"


async def sendEmail(recipents: str):
    msg = EmailMessage()
    msg["Subject"] = "大麦网(测试)身份验证邮件"
    msg["From"] = sender
    msg["To"] = recipents
    msg.set_content("测试邮件")
    try:
        async with aiosmtplib.SMTP(
            hostname="smtp.qq.com",
            port=587,
            username=sender,
            password=password,
            timeout=3,
            start_tls=True,
        ) as smtp:
            await smtp.send_message(msg, sender=sender, recipients=recipents)
        return True
    except Exception as e:
        logger.error(e)


async def generateToken(useranme: str, userid: int):
    expire_time_object = datetime.datetime.now() + datetime.timedelta(weeks=1)
    exp = int(expire_time_object.timestamp())
    payload = {"username": useranme, "userid": userid, "exp": exp}
    token = jwt.encode(payload, secret_key, algorithm)

    if isinstance(token, bytes):  # 转换token编码
        token = token.decode("utf-8")
        return token
    return token


async def validToken(token: str) -> str:
    try:
        token_data = jwt.decode(token, secret_key, algorithm)
        if token_data:
            userID = token_data.get("userid")
            if userID is None:
                raise ValueError("无效用户")
            return userID
    except Exception as e:
        logger.error(e)
        raise ValueError("无效凭证")


# 获取日志收集器
logger = logging.getLogger(name="damai")
# 设置日志登记
logger.setLevel(logging.DEBUG)

# 调用模块时,如果频繁多次错误,每次会添加handler,造成重复日志,每次都移除所有的handler,后面再重新添加
while logger.hasHandlers():
    for i in logger.handlers:
        logger.removeHandler(i)

# 对日志文件格式设置
formatter = logging.Formatter(
    "%(asctime)s-%(pathname)s[line:%(lineno)d]-%(levelname)s: %(message)s"
)
fh = logging.FileHandler(r"test_logger.log", encoding="utf-8")  # 日志文件路径，格式名称
fh.setLevel(logging.DEBUG)  # 日志打印级别
fh.setFormatter(fmt=formatter)
logger.addHandler(fh)

# 控制台输出控制
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.DEBUG)
ch.setFormatter(fmt=formatter)
logger.addHandler(ch)
