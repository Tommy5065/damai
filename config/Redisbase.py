import redis
import uuid
import time
import asyncio
from config.util import logger


# 异步连接工厂类
class RedisManager(object):
    @classmethod
    async def init(cls, db: int) -> object:
        instance = cls()
        pool = redis.ConnectionPool(
            host="localhost", port=6379, db=db, password="123456", decode_responses=True
        )
        redisObject = redis.Redis(connection_pool=pool)
        instance.object = redisObject
        return instance

    @staticmethod
    async def getDataRedis(connObject: object, key):
        cache = connObject.object.hgetall(key)
        return cache

    @staticmethod
    async def createCache(connObject: object, key: dict, map: dict):
        try:
            logger.debug(f"Redis 添加{key}")
            connObject.object.hset(key, mapping=map)
            connObject.object.expire(key, 360)
            logger.info("Redis 添加成功")
            return True
        except Exception as e:
            logger.error(e)

    @staticmethod
    async def deleteCache(connObject: object, key: dict):
        try:
            connObject.object.delete(key)
            logger.debug(f"Redis {key} 已删除")
        except Exception as e:
            raise RuntimeError(f"删除失败{e}")

    @staticmethod
    async def acuire_lock(
        connObject: object, lock_name: str, acquire_out_time=10, lock_time_out=30
    ):
        """获取分布式锁"""

        identifier = str(uuid.uuid4())
        lock_name = f"lock:{lock_name}"
        end = time.time() + acquire_out_time

        while time.time() < end:
            # 这个循环给用户良好的体验,一直拿不到所就返回错误,页面不会一直转圈圈等待
            if connObject.object.set(lock_name, identifier, ex=lock_time_out, nx=True):
                # 过期时间和创建锁写在一个命令里保证原子性防止无过期时间出现死锁,加上续期防止业务超时
                renew_exp = asyncio.create_task(
                    RedisManager.addExpTime(
                        connObject, lock_name, identifier, lock_time_out
                    )
                )
                return identifier, renew_exp
            asyncio.sleep(0.001)
        return None, None

    @staticmethod
    async def release_lock(connObject: object, lock_name: str, identifier: str):
        """释放锁"""

        # 编写LUA脚本,防止误删别人的锁
        unlock_script = b"""
            if redis.call("get",KEYS[1])==ARGV[1] then
                return redis.call("del",KEYS[1])
            else
                return 0
            end
        """
        lock_name = f"lock:{lock_name}"
        unlock = connObject.object.register_script(unlock_script)
        result = unlock(keys=[lock_name], args=[identifier])
        if result:
            logger.info("释放锁成功")
            return True
        else:
            return False

    @staticmethod
    async def addExpTime(
        connObject: object, lock_name: str, indentifier: str, lock_time_out: int
    ):
        """给锁延期"""
        # 过期的1/3时间段检查是否还持有锁
        renew_interval = lock_time_out * 2 // 3

        while True:
            await asyncio.sleep(renew_interval)

            # 编写LUA脚本判断当前用户是否还持有锁
            renew_script = b"""
                if redis.call("get",KEYS[1])==ARGV[1] then
                    return redis.call("expire",KEYS[1],ARGV[2])
                else
                    return 0
                end
            """
            lock_name = f"lock:{lock_name}"
            re_Expire = connObject.object.register_script(renew_script)
            result = re_Expire(keys=[lock_name], args=[indentifier, lock_time_out])
            if not result:
                break

    @staticmethod
    async def addExpTimeCancel(
        connObject: object, lock_name: str, identifier: str, renew_exp
    ):
        """关闭续期并释放锁"""
        try:
            if renew_exp:
                renew_exp.cancel()
                logger.info("关闭续期")
        except asyncio.CancelledError as e:
            logger.warning(f"关闭续期失败原因:{e}")

        finally:
            await RedisManager.release_lock(connObject, lock_name, identifier)
