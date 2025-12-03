from fastapi import FastAPI, HTTPException, status, Depends, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2AuthorizationCodeBearer
from typing import Annotated
from datetime import datetime
from .life import life
from consulTask.rabbitmq import rabbitMq
from orderService.utils import ValidToken, getIdenID, getGoodsInfo, getStock
from orderService.schema import CreateOrder, RushPurchaseInput

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


@order_service.get("/order/create/{goods_id}", response_model=CreateOrder)
async def createOrder(
    goods_id: Annotated[int, Path(..., title="the ID of the goods to get")],
    token=Depends(token),
):
    try:
        userID = await ValidToken(token)
        idenID = await getIdenID(userID["userid"], token)
        idenID = idenID["userIdenID"]
        goodsInfo = await getGoodsInfo(goods_id, token)
        if not idenID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="用户未填身份证信息"
            )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        # zfill把时间戳字符设置成6位,不足6位补0
        orderID = str(timestamp).zfill(8)
        return CreateOrder(idenID=idenID, goodsInfo=goodsInfo, orderID=orderID)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Redirect to login."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Service error:{e}",
        )


@order_service.post("/order/commit")
async def commitOrder(
    data: RushPurchaseInput,
    token=Depends(token),
):
    try:
        lockStock = await getStock(
            number=data.number,
            goodsID=data.goodsID,
            goodsName=data.goodsname,
            accessToken=token,
        )
        await rabbitMq.sendmessage(
            {"goodsID": data.goodsID, "goodsName": data.goodsname},
            exchange="order_event_exchange",
            routing_key="orderDelayqueue",
        )
        return lockStock
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{e}")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"goodsService error:{e}",
        )
