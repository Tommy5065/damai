import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from util import logger
from data_base import RedisManager, MysqlManager
from consulTask.main import Service


@asynccontextmanager
async def life(app: FastAPI):
    logger.info("userService服务开始启动")

    try:
        logger.info("开始连接数据库:mysql+redis")
        mysql_client = await MysqlManager.init("userservice")
        redis_client = await RedisManager.init(db=0)
        app.state.mysql_pool = mysql_client
        app.state.redis_client = redis_client

        userService = Service()
        await asyncio.sleep(5)
        userService.service_register("userService", "127.0.0.1", 8000)
        # 服务正常运行
        yield

        logger.info("userservice关闭,开始关闭数据库连接")
        await mysql_client.cursor.close()
        mysql_client.pool.close()
        await mysql_client.pool.wait_closed()
        userService.service_deregister("userService")

        logger.info("userService应用关闭成功")
    except Exception as e:
        logger.warning(f"启动时候的警告:{e}")
