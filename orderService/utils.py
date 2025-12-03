from fastapi import HTTPException, status
from typing import Dict, Any
import os
import sys
import json

sys.path.append(os.getcwd())
from consulTask.httpClien import HttpClient
from utils.log import logger


async def ValidToken(accessToken: str) -> Dict[str, Any]:
    try:
        userID = await HttpClient.request(
            "get",
            "userService",
            "/api/user/token",
            headers={"Authorization": f"Bearer {accessToken}"},
            requestName="orderService",
        )
        return userID
    except PermissionError as e:
        raise PermissionError(str(e)) from e

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"未知错误{e}"
        ) from e


async def getIdenID(userID: int, accessToken: str) -> Dict[str, Any]:
    try:
        idenID = await HttpClient.request(
            "post",
            "userService",
            f"/api/{userID}/iden_id",
            headers={"Authorization": f"Bearer {accessToken}"},
            requestName="orderService",
        )
        return idenID

    except ValueError as e:
        raise ValueError(str(e)) from e

    except Exception as e:
        raise HTTPException(str(e)) from e


async def getGoodsInfo(goodsID: int, accessToken: str) -> Dict[str, Any]:
    try:
        goodsInfo = await HttpClient.request(
            "get",
            "goodsService",
            f"/api/goods/{goodsID}/goodsInfo",
            headers={"Authorization": f"Bearer {accessToken}"},
            requestName="orderService",
        )
        return goodsInfo
    except Exception as e:
        raise HTTPException(str(e)) from e


async def getStock(number: int, goodsID: int, goodsName: str, accessToken: str):
    try:
        data = {"lockname:": goodsName, "goodsID": goodsID, "number": number}
        lockStockHttp = await HttpClient.request(
            "post",
            "goodsService",
            "/api/goods/purchase",
            headers={"Authorization": f"Bearer {accessToken}"},
            json=data,
            requestName="orderService",
        )
        return lockStockHttp
    except ValueError as e:
        raise ValueError(str(e)) from e

    except Exception as e:
        raise HTTPException(str(e)) from e
