from fastapi import FastAPI, Query, status, HTTPException, Depends, Form, Path, Request
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated
from utils.log import logger
from .life import lifespan
from config.Redisbase import RedisManager


goods_service = FastAPI(title="goodsService", lifespan=lifespan)
goods_service.add_middleware(CORSMiddleware, allow_methods=["*"], allow_origins=["*"])


async def get_db():
    """数据库连接依赖项"""
    # 从 app.state 获取连接池
    pool = goods_service.state.mysql_client
    try:
        yield pool
    finally:
        # 连接会自动归还到连接池，不需要手动关闭
        pass


async def get_redis():
    """Redis依赖项"""
    redis_client = goods_service.state.redis_client
    if not redis_client:
        raise HTTPException(status_code=500, detail="Redis客户端未初始化")
    yield redis_client


@goods_service.get("/goods/get", tags=["goods"])
async def showGoods(
    page: int = Query(default=1), offset: int = Query(default=20), db=Depends(get_db)
):
    # 翻页效果从数据库里进行翻页
    goods_datas = await db.getMysqlUser(
        db,
        sql=("SELECT * FROM goodstable order by goods_id limit %s,%s;"),
        param=((page - 1) * offset, offset),
    )
    res = []
    for info in goods_datas:
        info = {
            "商品名称": info[1],
            "演出地址": info[2],
            "库存量": info[3],
            "票价": info[4],
        }
        res.append(info)
    return res


@goods_service.post("/goods/check")
async def checkGoods(
    goodsid: Annotated[int, Form()], db=Depends(get_db), redis=Depends(get_redis)
):
    cache = await redis.getDataRedis(redis, key=f"goodsService:goodsid:{goodsid}")
    if cache:
        return {"status": status.HTTP_200_OK, "message": "缓存获取成功", "data": cache}

    logger.info("缓存未命中,防止缓存击穿用分布式锁")
    lock_name = str(goodsid)
    identifier, renew_exp = await RedisManager.acuire_lock(redis, lock_name)
    if identifier:
        try:
            detail = await db.getMysqlUser(
                db, sql="select * from goodstable where goods_id=%s", param=goodsid
            )
            logger.debug(detail)
            if detail:
                goods_name, goods_location, goods_num, goods_price = (
                    detail[1],
                    detail[2],
                    detail[3],
                    detail[4],
                )
                # 写入缓存
                await redis.createCache(
                    redis,
                    key=f"goodsService:goodsid:{goodsid}",
                    map={
                        "商品名称": goods_name,
                        "演出位置": goods_location,
                        "库存量": goods_num,
                        "票价": goods_price,
                    },
                )
                return {
                    "status": status.HTTP_200_OK,
                    "data": {
                        "商品名称": goods_name,
                        "演出位置": goods_location,
                        "库存量": goods_num,
                        "票价": goods_price,
                    },
                }

            logger.info(f"请求不存在数据{goodsid}")

            await redis.createCache(
                redis,
                key=f"goodsService:goodsid:{goodsid}",
                map="null",
            )
            return {"message": "无该商品"}
        except Exception as e:
            logger.warning(f"未生成锁错误原因:{e}")
        finally:
            try:
                await RedisManager.addExpTimeCancel(
                    redis, lock_name, identifier, renew_exp
                )
            except Exception as e:
                logger.critical(f"锁释放失败:{e}")


@goods_service.post("/api/goods/purchase")
async def rushPurchase(request: Request, redis=Depends(get_redis)):
    data = await request.json()
    lock_name, goodsID, number = [*data.values()]
    identifier, renew_task = await RedisManager.acuire_lock(redis, lock_name)
    if identifier:
        try:
            cache = await RedisManager.getDataRedis(
                redis, f"goodsService:goodsid:{goodsID}"
            )
            if int(cache["库存量"]) - number < 0:
                raise ValueError("库存量不足")
            else:
                redis.object.hincrby(
                    f"goodsService:goodsid:{goodsID}", "库存量", -number
                )
                logger.debug(cache["库存量"])
                return
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{e}")
        except Exception as e:
            logger.warning(f"业务错误:{e}")

        finally:
            try:
                await RedisManager.addExpTimeCancel(
                    redis, lock_name, identifier, renew_task
                )
            except Exception as e:
                logger.critical(f"释放锁失败:{e}")

    return {"message": "now is busy"}


@goods_service.get("/api/goods/{goodsID}/goodsInfo")
async def getGoodsInfoFromRedis(
    goodsID: Annotated[int, Path(...)], redis=Depends(get_redis)
):
    try:
        cache = await redis.getDataRedis(redis, key=f"goodsService:goodsid:{goodsID}")
        return cache
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"{e}"
        )
