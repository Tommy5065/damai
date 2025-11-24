from fastapi import FastAPI, Form, Requests
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated

order_service = FastAPI()
order_service.add_middleware(
    CORSMiddleware,
    allow_methods=["post", "get"],
    allow_orinigs=["http://localhost:8001"],
)


@order_service.post("/commit")
async def commitOrder(
    request: Requests,
    iden_id: Annotated[str | None, Form()],
    pay_way: Annotated[str | Alipay, Form()],
):
    OAuth = request.headers["Authorize"]
