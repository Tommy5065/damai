import aiosmtplib
import os
from dotenv import load_dotenv
from email.message import EmailMessage
from utils.log import logger

# 加载环境变量
load_dotenv()


async def sendEmail(recipents: str, max_retries=3):
    for attemp in range(max_retries):
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
            if attemp - 1:
                logger.error(
                    f"send email fail start retries {max_retries} times,the error is {e}"
                )
    return False
