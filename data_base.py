import aiomysql
import asyncio
import redis
from util import sendEmail


# 异步连接数据库封装在一个类里，不用重复写连接池了
class UserMysql(object):
    @classmethod
    async def init(cls) -> object:
        self = cls()
        pool = await aiomysql.create_pool(
            host="localhost",
            port=3306,
            user="root",
            password="123456",
            db="userservice",
            minsize=1,
            maxsize=10,
        )
        async with pool.acquire() as conn:
            cursor = await conn.cursor()
        self.pool = pool
        self.conn = conn
        self.cursor = cursor
        return self


async def getMysqlUser(connObject: object, sql: str, param: tuple) -> tuple:
    try:
        await connObject.cursor.execute(sql, param)
        return await connObject.cursor.fetchall()

    except aiomysql.MySQLError as e:
        print(e)

    finally:
        await connObject.cursor.close()
        connObject.pool.close()
        await connObject.pool.wait_closed()


async def registerMysqlUser(connObject: object, sql: str, param: tuple) -> tuple:
    try:
        await connObject.cursor.execute(sql, param)
        await connObject.conn.commit()
        return True
    except aiomysql.MySQLError as e:
        await connObject.conn.rollback()
        print(e)

    finally:
        await connObject.cursor.close()
        connObject.pool.close()
        await connObject.pool.wait_closed()


async def registerMysqlUserSendEmail(
    connObject: object, sql: str, email: str, param: tuple
) -> bool:
    task = await asyncio.gather(
        registerMysqlUser(connObject=connObject, sql=sql, param=param),
        sendEmail(email),
        return_exceptions=True,
    )
    print(task)
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


async def getDataRedis(connObject: object, key):
    cache = connObject.object.hgetall(key)
    return cache


async def createCache(connObject: object, key, map: dict):
    try:
        connObject.object.hset(key, mapping=map)
        connObject.object.expire(key, 36000)
        return True
    except Exception as e:
        raise RuntimeError(f"存储失败:{e}")
