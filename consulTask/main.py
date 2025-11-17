import consul


class Service:
    def __init__(self):
        self._concsul = consul.Consul(host="127.0.0.1", port=8500)

    def service_register(self, name: str, host: str, port: int):
        try:
            self._concsul.agent.service.register(
                name=name,
                service_id=name,
                address=host,
                port=port,
                check=consul.Check.tcp(
                    host=host, port=port, interval=5, timeout=30, deregister=30
                ),  # 心跳检查
            )
            print("service register success.")
        except Exception as e:
            print(f"register fail:{e}")
            raise RuntimeError("register fail")

    def service_found(self, name: str):
        try:
            service = self._concsul.agent.services()
            if service:
                service_http = "%s:%s" % (
                    service.get(name).get("Address"),
                    service.get(name).get("Port"),
                )
            return service_http
        except Exception as e:
            print(f"service get wrong fail:{e}")
            raise RuntimeError("service get wrong")

    def service_deregister(self, name: str):
        self._concsul.agent.service.deregister(service_id=name)
        print("deregister success.")
