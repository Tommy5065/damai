from main import Service
from util import logger
import json
import pika

rabbit_service = Service()

SERVICE_NAME = "rabbitmq"
HOST = "127.0.0.1"
PORT = 5672  # 走AMQU协议用5672端口

rabbit_service.service_register(SERVICE_NAME, HOST, PORT)


class RabbiMQ(object):
    @classmethod
    async def init(
        cls,
        host: str,
        port: str,
    ):
        logger.info("开始连接rabbitmq")
        instacne = cls()
        # 连接rabbitmq用户认证
        Credential = pika.PlainCredentials("guest", "guest")
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host, port=port, virtual_host="/", credentials=Credential
            )
        )
        instacne.conn = connection
        return instacne

    @staticmethod
    async def sendMessage(
        connObject: object, service_name: str, order_id: str, access_token: str
    ):
        try:
            channel = connObject.conn.channel()  # 开启管道
            channel.queue_bind(
                queue=service_name, routing_key=service_name, exchange="tcp1"
            )  # 一定要创建绑定！！！！不然又读取不了信息
            channel.queue_declare(queue=service_name, durable=True)  # 创建队列,持久化

            channel.exchange_declare(
                exchange="tcp1", exchange_type="direct", durable=True
            )

            # 构建消息格式
            messageFormat = {
                "orderId": order_id,
                "token": access_token,
                "identify": False,
            }
            logger.info("开始准备发送消息")
            channel.basic_publish(
                exchange="tcp1",
                routing_key=service_name,  # 路由键把交换机和队列绑定
                body=json.dumps(messageFormat),
                properties=pika.BasicProperties(delivery_mode=2),  # 消息持久化
            )
            logger.info("发送消息成功")
        except Exception as e:
            logger.critical(f"构建消息过程失败:{e}")

    @staticmethod
    async def consumeMessage(connObject: object, service_name: str, callback):
        try:
            channel = connObject.conn.channel()

            channel.basic_consume(
                queue=service_name,
                consumer_tag=f"{service_name}consume",
                on_message_callback=callback,
            )

            logger.info("准备消费阶段")
            channel.start_consuming()
        except Exception as e:
            logger.critical(f"消费信息失败:{e}")
