from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models.document import Document
from app.db.models.framework import Framework
from app.services.scoring import scoring_service
from app.core.security import get_current_user
from app.db.models.user import User

router = APIRouter(prefix='/scoring', tags=['Scoring'])


class ScoreResponse(BaseModel):
    framework_id: int | None
    framework_name: str | None
    compliance_score: float
    risk_level: str
    coverage: dict
    recommendations: list[str]


class TenantScoreResponse(BaseModel):
    tenant_id: int
    overall_score: float
    risk_level: str
    frameworks: list[dict]


@router.get('/document/{doc_id}', response_model=ScoreResponse)
async def score_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == current_user.tenant_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail='Document not found')

    fw = None
    if doc.framework_id:
        fw_result = await db.execute(select(Framework).where(Framework.id == doc.framework_id))
        fw = fw_result.scalars().first()

    scoring = await scoring_service.score_document(db, doc, fw)
    return ScoreResponse(
        framework_id=doc.framework_id,
        framework_name=fw.name if fw else None,
        compliance_score=scoring.score,
        risk_level=scoring.risk_level,
        coverage=scoring.coverage,
        recommendations=scoring.recommendations,
    )


@router.get('/tenant', response_model=TenantScoreResponse)
async def tenant_score(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fw_result = await db.execute(
        select(Framework).where(Framework.tenant_id == current_user.tenant_id)
    )
    frameworks = fw_result.scalars().all()

    fw_scores = []
    all_scores = []
    for fw in frameworks:
        score = fw.compliance_score or 0.0
        all_scores.append(score)
        fw_scores.append({'id': fw.id, 'name': fw.name, 'score': score})

    overall = round(sum(all_scores) / len(all_scores), 1) if all_scores else 0.0
    from app.services.scoring import score_to_risk
    return TenantScoreResponse(
        tenant_id=current_user.tenant_id,
        overall_score=overall,
        risk_level=score_to_risk(overall / 100),
        frameworks=fw_scores,
    )


@router.post('/mock')
async def mock_score():
    """Quick demo endpoint — returns a fake compliance score."""
    import random
    score = round(random.uniform(40, 95), 1)
    return {
        'compliance_score': score,
        'risk_level': 'low' if score >= 80 else 'medium' if score >= 60 else 'high',
        'note': 'This is a mock score for demo purposes',
    }
