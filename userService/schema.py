from pydantic import BaseModel
from fastapi import Body


class Login(BaseModel):
    username: str = Body(..., embed=True)
    password: str = Body(..., embed=True)


class Register(Login):
    email: str = Body(..., embed=True)


class Token(BaseModel):
    token: str = Body(...)
    type: str = "Bearer"
