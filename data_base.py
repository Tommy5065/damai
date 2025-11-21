import aiomysql
import asyncio
import redis
from util import sendEmail, logger


# 异步连接数据库封装在一个类里，不用重复写连接池了
class MysqlManager(object):
    @classmethod
    async def init(cls, dbname) -> object:
        self = cls()
        pool = await aiomysql.create_pool(
            host="localhost",
            port=3306,
            user="root",
            password="123456",
            db=dbname,
            minsize=1,
            maxsize=10,
        )
        async with pool.acquire() as conn:
            cursor = await conn.cursor()
        self.pool = pool
        self.conn = conn
        self.cursor = cursor
        return self

    @staticmethod
    async def getMysqlUser(connObject: object, sql: str, param: tuple) -> tuple:
        try:
            logger.debug(f"开始查询{param}")
            await connObject.cursor.execute(sql, param)
            return await connObject.cursor.fetchall()

        except aiomysql.MySQLError as e:
            logger.error(e)

    @staticmethod
    async def registerMysqlUser(connObject: object, sql: str, param: tuple) -> tuple:
        try:
            await connObject.cursor.execute(sql, param)
            await connObject.conn.commit()
            return True
        except aiomysql.MySQLError as e:
            await connObject.conn.rollback()
            logger.error(e)


@staticmethod
async def updateMysqlUser(connObject: object, sql: str, param: tuple) -> tuple:
    try:
        await connObject.cursor.execute(sql, param)
        await connObject.conn.commit()
        return True
    except aiomysql.MySQLError as e:
        await connObject.conn.rollback()
        logger.error(e)
        return False


async def registerMysqlUserSendEmail(
    connObject: object, sql: str, email: str, param: tuple
) -> bool:
    task = await asyncio.gather(
        MysqlManager.registerMysqlUser(connObject=connObject, sql=sql, param=param),
        sendEmail(email),
        return_exceptions=True,
    )
    logger.info(task)
    if task[0] is True and task[1] is True:
        return task
    return False


# 异步连接工厂类
class RedisManager(object):
    @classmethod
    async def init(cls, db: int) -> object:
        instance = cls()
        pool = redis.ConnectionPool(
            host="localhost", port=6379, db=db, password=123456, decode_responses=True
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
            connObject.object.expire(key, 3600)
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
