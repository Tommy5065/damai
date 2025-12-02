from contextlib import asynccontextmanager
from fastapi import FastAPI
from utils.log import logger
from config.data_base import MysqlManager
from config.Redisbase import RedisManager
from consulTask.main import service
from consulTask.httpClien import HttpClient
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
        await service.service_register("orderService", "127.0.0.1", 8002)

        yield

    except Exception as e:
        logger.warning(f"orderservice启动过程的BUG:{e}")

    finally:
        logger.info("orderservice关闭开始关闭数据库连接")
        await mysql_client.cursor.close()
        mysql_client.pool.close()
        await mysql_client.pool.wait_closed()
        await HttpClient.close()
        await service.service_deregister("orderService")
