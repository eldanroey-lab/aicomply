from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    priority: str = 'medium'
    due_date: Optional[date] = None
    assignee_id: Optional[int] = None
    framework_id: Optional[int] = None
    control_id: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[date] = None
    assignee_id: Optional[int] = None


class TaskRead(TaskBase):
    id: int
    status: str
    tenant_id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime
    model_config = {'from_attributes': True}
