import aiohttp
import sys
import os
from typing import Dict

sys.path.append(os.getcwd())
from consulTask.main import service
from utils.log import logger


class AsyncHttpClient:
    def __init__(self):
        # 初始化请求对话
        self.session = None

    async def getSession(self):
        if self.session is None:
            # 设置超时时间
            timeout = aiohttp.ClientTimeout(10)
            self.session = aiohttp.ClientSession(timeout=timeout)

    async def request(
        self,
        method: str,
        serviceName: str,
        path: str,
        headers: Dict[str, str] = None,
        **kwargs,
    ):
        """向其他服务异步调用接口"""

        baseUrl = await service.service_found(serviceName, kwargs["requestName"])
        if not baseUrl:
            raise Exception(f"未发现{serviceName}服务")
        url = f"{baseUrl}{path}"

        try:
            await self.getSession()
            async with self.session.request(method, url, headers=headers) as response:
                # 用来抛出错误响应码，进行异常处理,不返回错的响应体
                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientResponseError as e:
            if e.status == 401:
                raise PermissionError("用户重新登录")
            if e.status == 400:
                raise ValueError("用户未填身份证信息")

        except aiohttp.ClientTimeout:
            raise TimeoutError(f"{serviceName}响应超时")

        except aiohttp.ClientError as e:
            # 捕获其他aiohttp错误
            raise Exception(f"Request failed: {e}")

    async def close(self):
        """手动关闭session"""
        if self.session:
            await self.session.close()


# 全局http客户端
HttpClient = AsyncHttpClient()
