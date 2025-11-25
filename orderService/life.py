from contextlib import asynccontextmanager
from fastapi import FastAPI
from config.util import logger
from config.data_base import RedisManager, MysqlManager
from consulTask.main import Service
from consulTask.rabbitmq import RabbiMQ


@asynccontextmanager
async def life(app: FastAPI):
    logger.info("orderservice服务开始启动")

    try:
        logger.info("开始连接数据库")
        mysql_client = await MysqlManager.init("orderservice")
        redis_client = await RedisManager.init(db=2)
        app.state.mysql_pool = mysql_client
        app.state.redis_client = redis_client

        orderService = Service()
        orderService.service_register("orderservice", "127.0.0.1", 8002)

        logger.info("开始连接mq服务器")
        rabbit_http = orderService.service_found("rabbitmq")
        host = rabbit_http.split(":")[0]
        port = rabbit_http.split(":")[1]
        rabbit = await RabbiMQ.init(host, port)
        app.state.rabbit = rabbit

        yield

    except Exception as e:
        logger.warning(f"orderservice启动过程的BUG:{e}")

    finally:
        logger.info("orderservice关闭开始关闭数据库连接")
        await mysql_client.cursor.close()
        mysql_client.pool.close()
        await mysql_client.pool.wait_closed()
        orderService.service_deregister("orderservice")
        rabbit.conn.close()
