from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.chatcopilot import chat_copilot_service
from app.core.security import get_current_user
from app.db.models.user import User

router = APIRouter(prefix='/copilot', tags=['AI Copilot'])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    reply: str


@router.post('/chat', response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reply = await chat_copilot_service.chat(
        db=db,
        tenant_id=current_user.tenant_id,
        message=payload.message,
        history=payload.history,
    )
    return ChatResponse(reply=reply)
