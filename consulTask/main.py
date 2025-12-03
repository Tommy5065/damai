import consul
import os
import sys

sys.path.append(os.getcwd())
from utils.log import logger


class Service:
    def __init__(self):
        self._consul = consul.Consul(host="127.0.0.1", port=8500)

    async def service_register(self, name: str, host: str, port: int):
        try:
            logger.debug(f"{name}请求注册服务")
            self._consul.agent.service.register(
                name=name,
                service_id=name,
                address=host,
                port=port,
                check=consul.Check.tcp(
                    host,
                    port,
                    interval=30,
                    timeout=15,
                    deregister=15,
                ),  # 心跳检查
            )
            logger.info(f"{name} register success.")
            return True
        except Exception as e:
            logger.error(f"register fail:{e}")
            return False

    async def service_found(self, name: str, requestName: str = None):
        try:
            logger.debug(f"{requestName}请求{name}服务地址")
            service = self._consul.agent.services()
            if service:
                service_http = "%s:%s" % (
                    service.get(name).get("Address"),
                    service.get(name).get("Port"),
                )
            logger.debug(f"{requestName}请求{name}服务地址成功")
            return f"http://{service_http}"
        except Exception as e:
            logger.error(f"found service fail:{e}")
            return None

    async def service_deregister(self, name: str):
        logger.debug(f"注销{name}服务地址")
        self._consul.agent.service.deregister(service_id=name)
        logger.debug(f"请求{name}服务地址注销成功")


# 设置一个全局服务注册变量
service = Service()
