from email.message import EmailMessage
import aiosmtplib
import jwt
import datetime

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
        raise e


async def generateToken(useranme: str):
    expire_time_object = datetime.datetime.now() + datetime.timedelta(weeks=1)
    exp = int(expire_time_object.timestamp())
    payload = {"username": useranme, "exp": exp}
    token = jwt.encode(payload, secret_key, algorithm)

    if isinstance(token, bytes):  # 转换token编码
        token = token.decode("utf-8")
        return token
    return token


async def validToken(token: str):
    try:
        token_data = jwt.decode(token, secret_key, algorithm)
        if token_data:
            username = token_data.get(token_data)
            if username is None:
                raise ValueError("无效用户")
            return username
    except Exception as e:
        print(e)
        raise ValueError("无效凭证")


# 使用asynic.run报：
# Exception ignored in: <function _ProactorBasePipeTransport.__del__ at 0x0000025EBBAF67A0>
# RuntimeError: Event loop is closed
# 原因：asynico对window系统不友好，默认使用_ProactorBasePipeTransport，并且在程序退出释放内存时自动调用了其__del__ 方法

# 解决方案，更换启动程序
"""
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(sendEmail("19985105065@163.com"))
"""
