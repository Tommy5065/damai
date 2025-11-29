from fastapi import FastAPI, Form, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from typing import Annotated
import uuid
from .life import life
from consulTask.rabbitmq import RabbiMQ

order_service = FastAPI(lifespan=life)
order_service.add_middleware(
    CORSMiddleware,
    allow_methods=["post", "get"],
    allow_origins=["*"],
)

token = OAuth2AuthorizationCodeBearer(
    authorizationUrl="http://localhost:8000/login",
    tokenUrl="http://localhost:8000/login",
)


@order_service.post("/commit")
async def commitOrder(
    iden_id: Annotated[str | None, Form()],
    token=Depends(token),
):
    order_id = str(uuid.uuid4())

    message = {"token": token, "orderID": order_id, "idenID": iden_id}
    await RabbiMQ.sendmessage(routing_key="valideOrderToken", message=message)
