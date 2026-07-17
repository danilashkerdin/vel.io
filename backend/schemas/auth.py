import re
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    is_advertiser: bool = False

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Пароль должен содержать минимум 6 символов")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if len(v) < 2:
            raise ValueError("Имя пользователя должно содержать минимум 2 символа")
        if len(v) > 50:
            raise ValueError("Имя пользователя слишком длинное (максимум 50 символов)")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str


class AuthResponse(BaseModel):
    token: str
    user: UserResponse
