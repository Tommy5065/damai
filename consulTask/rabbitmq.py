import json
import aio_pika
import os
import sys
import asyncio
from typing import Optional
from aio_pika.pool import Pool

sys.path.append(os.getcwd())
from utils.log import logger


# 单例模式在同一个进程中，节省重复创建多个相同类的开销
class RabbiMQManage(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        """控制实例创建"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self._isinitialize = False
        self.connPool: Optional[Pool] = None
        self.channelPool: Optional[Pool] = None

    async def initilize(self):
        """创建链接的工厂函数"""
        if self._isinitialize:
            raise RuntimeError("RabbitMQ已初始化")

        async def createConnection():
            logger.info("创建rabbiymq新链接")
            # 使用connect_robust可以自动重连
            return await aio_pika.connect_robust(
                host="localhost",
                port=5672,
                login="fastapi",
                password="fastapi",
                virtualhost="fastAPI",
            )

        async def createChannel(conn):
            logger.info("创建rabbiymq新信道")
            async with conn.acquire() as conn:
                channel = await conn.channel()
                await channel.set_qos(prefetch_count=1)
                return channel

        self.connPool = Pool(createConnection, max_size=2)
        self.channelPool = Pool(
            createChannel,
            self.connPool,
            max_size=10,
        )
        self._isinitialize = True

    async def setQueueAndBings(self):
        try:
            connection = await aio_pika.connect_robust(
                "amqp://fastapi:fastapi@localhost:5672/fastAPI"
            )
            async with connection:
                channel = await connection.channel()  # 开启管道

                """  声明订单情况交换机,方便通过不同路由,路由到对应的队列  """
                order_event_exchange = await channel.declare_exchange(
                    "order_event_exchange",
                    type=aio_pika.ExchangeType.TOPIC,
                    durable=True,
                )

                orderDelayqueue = await channel.declare_queue(
                    "orderDelayqueue", durable=True
                )  # 声明延迟消息队列(相当于是死信队列,当死信队列里有消息就路由到对应的库存队列,实现数据一致性)
                await orderDelayqueue.bind(
                    order_event_exchange, routing_key="orderDelayqueue"
                )

                paystate = await channel.declare_queue(
                    "paystate",
                    durable=True,
                    arguments={
                        "x-dead-letter-exchange": "order_event_exchange",
                        "x-dead-letter-routing-key": "orderDelayqueue",
                        "x-max-length": 10,
                        "x-message-ttl": 10000,  # 消息10秒后过期进入死信,队列TTL
                    },
                )  # 正常队列,有点特殊没有对应的消费者,靠消息过期后在死信消费者中查看支付状态
                await paystate.bind(
                    order_event_exchange,
                    routing_key="pay*",
                )

                cancelOrder = await channel.declare_queue(
                    "cancelOrder", durable=True
                )  # 已付款取消订单不用经过死信队列转发回滚库存的情况,直接转发消息到库存的回滚队列里
                await cancelOrder.bind(order_event_exchange, routing_key="cancel*")

                """  声明库存情况交换机,方便通过不同的路由,路由到对应的队列处理消息  """
                stock_event_exchange = await channel.declare_exchange(
                    "stock_event_exchange", type=aio_pika.ExchangeType.TOPIC
                )

                rollbackRedis = await channel.declare_queue(
                    name="rollbackRedis", durable=True
                )  # 声明仅回滚缓存的redis队列
                await rollbackRedis.bind(
                    stock_event_exchange, routing_key="expire*"
                )  # 死信队列和交换机绑定

                rollbackMysql = await channel.declare_queue(
                    name="rollbackMysql", durable=True
                )  # 声明需要回滚数据库包括回滚缓存的队列处理
                await rollbackMysql.bind(stock_event_exchange, routing_key="cancel*")

                decreateMysql = await channel.declare_queue(
                    name="decreateMysql", durable=True
                )
                await decreateMysql.bind(
                    stock_event_exchange, routing_key="decreate*"
                )  # 付款成功,正常更改数据库库存
        finally:
            await connection.close()

    async def sendmessage(self, message: dict, exchange: str, routing_key: str):
        """异步发送消息"""
        async with self.channelPool.acquire() as channel:
            exchange = await channel.declare_exchange(
                exchange, type=aio_pika.ExchangeType.TOPIC, durable=True
            )  # 声明对应的交换机方便发送消息
        logger.info("消息构建完毕,准备发送")
        await exchange.publish(
            aio_pika.Message(body=json.dumps(message).encode(), expiration=1000),
            routing_key=routing_key,
        )
        logger.info("发送成功")

    async def orderDelayConsume(self, mysqlOrder: object):
        logger.info("开启订单私信后端")
        try:
            async with self.channelPool.acquire() as channel:
                orderDelayqueue = await channel.declare_queue(
                    "orderDelayqueue", durable=True
                )
                # 无限循环会阻塞我的项目启动
                async with orderDelayqueue.iterator() as orderDelayqueue_list:
                    async for message in orderDelayqueue_list:
                        async with message.process():
                            data = json.loads(message.body.decode())
                            # 查询订单记录的pay字段是否成功
                            result = await mysqlOrder.checkMysqlUser(
                                mysqlOrder,
                                sql="select pay_success from ordertable where order_uuid=%s",
                                param=(data.get("orderID", None),),
                            )
                            if result[0] == 1:
                                # 已支付订单就减少数据库的真实库存量
                                await self.sendmessage(
                                    message={
                                        "goodsName": data.get("goodsName", None),
                                        "payNumber": data.get("payNumber", 0),
                                        "goodsID": data.get("goodsID", 0),
                                    },
                                    exchange="stock_event_exchange",
                                    routing_key="decreate*",
                                )
                            else:
                                # 未支付回滚商品redis缓存
                                await self.sendmessage(
                                    message={
                                        "goodsID": data.get("goodsID", None),
                                        "payNumber": data.get("payNumber", 0),
                                    },
                                    exchange="stock_event_exchange",
                                    routing_key="expire*",
                                )
        except Exception as e:
            logger.critical(f"订单死信消费者运行错误:{e}")

    async def stockConsumeManager(self, mysqlStock: object, redisStock: object):
        logger.info("库存管理消费后台")
        try:

            async def rollbackRedisConsume(redisStock=redisStock):
                logger.info("库存缓存回滚消费者开启")
                try:
                    async with self.channelPool.acquire() as channel:
                        rollbackRedis = await channel.declare_queue(
                            name="rollbackRedis", durable=True
                        )
                        async with rollbackRedis.iterator() as rollbackRedis_list:
                            async for message in rollbackRedis_list:
                                async with message.process():
                                    data = json.loads(message.body.decode())
                                    redisStock.object.hincrby(
                                        f"goodsService:goodsid:{data.get('goodsID', None)}",
                                        "库存量",
                                        data.get("payNumber", 0),
                                    )
                except asyncio.exceptions.CancelledError:
                    pass
                except Exception as e:
                    logger.critical(f"库存缓存回滚消费者运行异常:{e}")

            async def decreateMysqlStockConsume(mysqlStock=mysqlStock):
                logger.info("库存数据库消费者开启")
                try:
                    async with self.channelPool.acquire() as channel:
                        decreateMysql = await channel.declare_queue(
                            name="decreateMysql", durable=True
                        )
                        async with decreateMysql.iterator() as decreateMysql_list:
                            async for message in decreateMysql_list:
                                async with message.process():
                                    data = json.loads(message.body.decode())
                                    await mysqlStock.cursor.execute(
                                        "UPDATE goodstable SET goods_number=goods_number-%s WHERE goods_name=%s AND goods_number>=0;",
                                        (
                                            data.get("payNumber", 0),
                                            data.get("goodsName", None),
                                        ),
                                    )
                                    if mysqlStock.cursor.rowcount == 0:
                                        raise ValueError("mysql的库存量不足")
                                    await mysqlStock.conn.commit()
                except ValueError as e:
                    await mysqlStock.conn.rollback()
                    logger.warning(f"{e}")

                except Exception as e:
                    await mysqlStock.conn.rollback()
                    logger.warning(f"库存Mysql操作运行错误:{e}")

            asyncio.create_task(
                rollbackRedisConsume(redisStock), name="rollbackRedisConsume"
            )
            asyncio.create_task(
                decreateMysqlStockConsume(mysqlStock),
                name="decreateMysqlStockConsume",
            )

        except Exception as e:
            logger.critical(f"库存管理消费者后台运行错误:{e}")

    async def close(self):
        logger.info("开始关闭mq链接")
        if self.channelPool:
            await self.channelPool.close()

        if self.connPool:
            await self.connPool.close()


rabbitMQ = RabbiMQManage()
#     await rabbitMQ.setQueueAndBings()
