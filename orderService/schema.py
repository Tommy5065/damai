from pydantic import BaseModel
from typing import Dict, Any


class CreateOrder(BaseModel):
    idenID: str
    userID: int
    goodsInfo: Dict[str, Any]


class RushPurchaseInput(BaseModel):
    goodsname: str
    goodsID: int
    userID: int
    number: int
