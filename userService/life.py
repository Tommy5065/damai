import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from utils.log import logger
from config.data_base import MysqlManager
from config.Redisbase import RedisManager
from consulTask.main import service


@asynccontextmanager
async def life(app: FastAPI):
    logger.info("userService服务开始启动")

    try:
        logger.info("开始连接数据库:mysql+redis")
        task1 = asyncio.create_task(MysqlManager.init("userservice"))
        task2 = asyncio.create_task(RedisManager.init(db=0))
        mysql_client, redis_client = await asyncio.gather(
            task1, task2, return_exceptions=True
        )
        app.state.mysql_pool = mysql_client
        app.state.redis_client = redis_client
        await service.service_register("userService", "127.0.0.1", 8000)

        yield

    except Exception as e:
        logger.warning(f"启动时候的警告:{e}")

    finally:
        logger.info("userservice关闭,开始关闭数据库连接")
        await mysql_client.cursor.close()
        mysql_client.pool.close()
        await mysql_client.pool.wait_closed()
        await service.service_deregister("userService")
