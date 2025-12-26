import aiomysql
from utils.log import logger


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
    async def checkMysqlUser(connObject: object, sql: str, param: tuple):
        try:
            logger.debug(f"查询{param}")
            await connObject.cursor.execute(sql, param)
            return await connObject.cursor.fetchone()
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
    async def updateMysqlUser(connObject: object, sql: str, param: tuple) -> bool:
        try:
            await connObject.cursor.execute(sql, param)
            await connObject.conn.commit()
            return True
        except aiomysql.MySQLError as e:
            await connObject.conn.rollback()
            logger.error(e)
            return False

    async def close(self):
        logger.info("开始关闭数据库")
        await self.cursor.close()
        self.pool.close()
        await self.pool.wait_closed()
