import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from utils.log import logger
from config.data_base import MysqlManager
from config.Redisbase import RedisManager
from consulTask.main import service
from consulTask.httpClien import HttpClient
from consulTask.rabbitmq import rabbitMQ


@asynccontextmanager
async def life(app: FastAPI):
    logger.info("orderservice服务开始启动")
    try:
        logger.info("开始连接数据库")
        task1 = asyncio.create_task(MysqlManager.init("orderservice"))
        task2 = asyncio.create_task(RedisManager.init(db=2))
        mysql_client, redis_client = await asyncio.gather(task1, task2)
        app.state.mysql_pool = mysql_client
        app.state.redis_client = redis_client
        await service.service_register("orderService", "127.0.0.1", 8002)
        await rabbitMQ.initilize()
        # 消费者开启后台任务
        rabbit_consume_task = asyncio.create_task(
            rabbitMQ.orderDelayConsume(mysql_client)
        )
        # 保存任务，应用结束关闭后台
        app.state.rabbit_consume_task = rabbit_consume_task
        yield

    except Exception as e:
        logger.warning(f"orderservice启动过程的BUG:{e}")

    finally:
        logger.info("orderservice关闭开始关闭数据库连接")
        await HttpClient.close()
        await service.service_deregister("orderService")
        if hasattr(app.state, "rabbit_consume_task"):
            app.state.rabbit_consume_task.cancel()
            try:
                # 一定要等待任务取消,任务取消是需要时间的！不然就先关闭连接池了
                await asyncio.wait_for(app.state.rabbit_consume_task, timeout=5)
            except TimeoutError as e:
                logger.debug(f"时间超时{e}")
            # 在取消任务的时候本来就会抛出cancelledError异常一定要捕获
            # 如果不这么做会打印warning，异步task失败没有被异常处理
            except asyncio.exceptions.CancelledError:
                pass
            except Exception as e:
                logger.debug(f"关闭消费者出错了:{e}")
        await mysql_client.close()
        await rabbitMQ.close()
