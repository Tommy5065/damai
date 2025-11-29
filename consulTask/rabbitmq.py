import json
import aio_pika
import os
import sys


sys.path.append(os.getcwd())
from utils.log import logger


class RabbiMQ(object):
    def __init__(self):
        pass

    @staticmethod
    async def setQueueAndBings():
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
        async with connection:
            channel = await connection.channel()  # 开启管道
            await channel.declare_exchange(name="tcp1", durable=True)  # 声明交换机

            # 队列和路由配置
            QUEUE_CONFIG = {
                "userService": {
                    "routing_key": ["valideOrderToken"],
                    "callBack": "handlerUser",
                },
                "orderService": {
                    "routing_key": ["getuserID", "paySuccess", "payFailed"],
                    "callBack": "handlerOrder",
                },
                "goodsService": {
                    "routing_key": ["createOrder", "cancelOrder"],
                    "callBack": "handlerGoods",
                },
            }

            for queneName, config in QUEUE_CONFIG.items():
                await channel.queue_declare(
                    queue=queneName, durable=True
                )  # 创建队列,持久化
                for routing_key in config["routing_key"]:
                    await channel.queue_bind(
                        queue=queneName, routing_key=routing_key, exchange="tcp1"
                    )
                    logger.debug(f"{routing_key}路由绑定{queneName}建")

    @staticmethod
    async def sendmessage(message: dict, routing_key: str):
        """异步发送消息"""
        connection = await aio_pika.connect_robust("amqp://guest:guest@localhost:5672/")
        async with connection:
            channel = await connection.channel()
            exchange = await channel.declare_exchange(
                "tcp1", durable=True
            )  # 声明交换机了才好发消息

            logger.info("消息构建完毕,准备发送")
            await exchange.publish(
                aio_pika.Message(body=json.dumps(message).encode()),
                routing_key=routing_key,
            )
            logger.info("发送成功")
