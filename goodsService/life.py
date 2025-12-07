from contextlib import asynccontextmanager
from fastapi import FastAPI
import asyncio
from utils.log import logger
from config.data_base import MysqlManager
from config.Redisbase import RedisManager
from consulTask.main import service
from consulTask.rabbitmq import rabbitMQ


async def CacheWarmuService(connMysql: object, connRedis: object, param: tuple):
    try:
        logger.info("开始预热缓存热门商品")
        # 获取热门商品列表
        goods_list = await getCacheGoods(connMysql, param=param)

        # 设置并发创建缓存
        tasks = []
        for index, goods in goods_list:
            key = f"goodsService:goodsid:{index}"
            exist = await RedisManager.getDataRedis(connRedis, key=key)
            if exist:
                continue

            task = RedisManager.createCache(
                connRedis,
                key=key,
                map={
                    "商品名称": goods["商品名称"],
                    "演出地址": goods["演出地址"],
                    "库存量": goods["库存量"],
                    "票价": goods["票价"],
                },
            )
            tasks.append(task)
        res = await asyncio.gather(*tasks, return_exceptions=True)

        # 统计多少商品缓存成功，使用生成器
        success_num = sum(1 for r in res if r is True)
        fail_num = len(tasks) - success_num
        logger.info(f"{success_num}个缓存成功,{fail_num}个缓存失败")
    except Exception as e:
        logger.warning(f"预热失败{e}")


async def getCacheGoods(
    connObject: object, param: tuple, goods_list: list = []
) -> list:
    """从数据库中获取"""
    try:
        logger.info("从数据库获取热门商品")
        goods_datas = await MysqlManager.getMysqlUser(
            connObject, sql="SELECT * FROM goodstable where goods_id < %s;", param=param
        )
        for info in goods_datas:
            index = info[0]
            info = {
                "商品名称": info[1],
                "演出地址": info[2],
                "库存量": info[3],
                "票价": info[4],
            }
            goods_list.append([index, info])
        return goods_list

    except Exception as e:
        logger.warning(f"从数据库中获取热门商品失败:{e}")


# 异步上下文管理器
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("goodsService开始启动")

    try:
        logger.info("连接数据库:mysql+redis")
        mysql_client = await MysqlManager.init("goodsservice")
        redis_client = await RedisManager.init(db=1)
        app.state.mysql_client = mysql_client
        app.state.redis_client = redis_client
        # 异步启动
        asyncio.create_task(CacheWarmuService(mysql_client, redis_client, (21)))
        logger.info("预热已异步开启")

        logger.info("开始注册goodsService服务")
        await service.service_register("goodsService", "127.0.0.1", 8001)
        await rabbitMQ.initilize()
        # 开启消费者任务
        stockConsumeManager = asyncio.create_task(
            rabbitMQ.stockConsumeManager(mysql_client, redis_client)
        )
        app.state.stockConsumeManager = stockConsumeManager

        yield

    except Exception as e:
        logger.warning(f"启动时候的警告:{e}")

    finally:
        await service.service_deregister("goodsService")
        if hasattr(app.state, "stockConsumeManager"):
            app.state.stockConsumeManager.cancel()
            try:
                await asyncio.wait_for(app.state.stockConsumeManager, timeout=5)
            except TimeoutError:
                logger.info("关闭库存消费者后台超时")
            except asyncio.exceptions.CancelledError:
                pass
        await mysql_client.close()
        await rabbitMQ.close()
