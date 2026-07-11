from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Any


class DocumentRead(BaseModel):
    id: int
    filename: str
    original_name: str
    file_type: str
    file_size: Optional[int] = None
    tenant_id: int
    uploader_id: int
    framework_id: Optional[int] = None
    compliance_score: Optional[float] = None
    risk_level: Optional[str] = None
    ai_summary: Optional[str] = None
    ai_gaps: Optional[list] = None
    ai_tags: Optional[list] = None
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = {'from_attributes': True}


class DocumentUpdate(BaseModel):
    framework_id: Optional[int] = None
