from fastapi import FastAPI, Form, HTTPException, status, Depends, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from typing import Annotated, Dict, Any
import uuid
from .life import life
from consulTask.rabbitmq import RabbiMQ
from orderService.utils import ValidToken, getIdenID
from consulTask.httpClien import HttpClient

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


@order_service.get("/commit/{goods_id}")
async def commitOrder(
    goods_id: Annotated[int, Path(..., title="the ID of the goods to get")],
    token=Depends(token),
):
    try:
        userID = await ValidToken(token)
        idenID = await getIdenID(userID["userid"], token)

        if not idenID["userIdenID"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户未填身份证信息"
            )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Redirect to login."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"userService error:{e}",
        )
