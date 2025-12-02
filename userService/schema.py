from pydantic import BaseModel, EmailStr
from fastapi import Body


class Register(BaseModel):
    username: str
    password: str
    email: EmailStr


class Token(BaseModel):
    token: str = Body(...)
    type: str = "Bearer"


class MessageOut(BaseModel):
    message: str


class CheckInfoOut(BaseModel):
    username: str
    email: EmailStr
    idenID: str = None


class userIDOut(BaseModel):
    userid: int


class userIdenIDOut(BaseModel):
    userIdenID: str
