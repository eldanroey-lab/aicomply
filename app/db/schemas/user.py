from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    domain: Optional[str] = None
    plan: str = 'free'


class TenantCreate(TenantBase):
    pass


class TenantRead(TenantBase):
    id: int
    is_active: bool
    created_at: datetime
    model_config = {'from_attributes': True}


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = 'member'


class UserCreate(UserBase):
    password: Optional[str] = None  # None for OAuth users
    tenant_id: int


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserRead(UserBase):
    id: int
    is_active: bool
    tenant_id: int
    avatar_url: Optional[str] = None
    created_at: datetime
    model_config = {'from_attributes': True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
