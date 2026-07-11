from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


class ControlItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    weight: float = 1.0


class FrameworkBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    version: Optional[str] = None
    controls: Optional[list[ControlItem]] = []


class FrameworkCreate(FrameworkBase):
    pass


class FrameworkUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    controls: Optional[list[ControlItem]] = None


class FrameworkRead(FrameworkBase):
    id: int
    tenant_id: int
    compliance_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    model_config = {'from_attributes': True}
