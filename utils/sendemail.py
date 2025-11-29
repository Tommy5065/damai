from email.message import EmailMessage
import aiosmtplib
import os
from utils.log import logger


async def sendEmail(recipents: str):
    msg = EmailMessage()
    msg["Subject"] = "大麦网(测试)身份验证邮件"
    msg["From"] = os.getenv("SENDER")
    msg["To"] = recipents
    msg.set_content("测试邮件")
    try:
        async with aiosmtplib.SMTP(
            hostname="smtp.qq.com",
            port=587,
            username=os.getenv("SENDER"),
            password=os.getenv("PASSWORD"),
            timeout=3,
            start_tls=True,
        ) as smtp:
            await smtp.send_message(
                msg, sender=os.getenv("SENDER"), recipients=recipents
            )
        return True
    except Exception as e:
        logger.error(e)
