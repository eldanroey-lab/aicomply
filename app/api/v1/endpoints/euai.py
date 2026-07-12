"""
EU AI Act compliance API endpoints.

Endpoints:
  POST   /euai/systems                          — Register an AI system
  GET    /euai/systems                          — List all systems for tenant
  GET    /euai/systems/{id}                     — Get system details
  PATCH  /euai/systems/{id}                     — Update system metadata
  POST   /euai/systems/{id}/classify            — Run risk classification
  POST   /euai/systems/{id}/assessments         — Start conformity assessment
  GET    /euai/systems/{id}/assessments         — List assessments
  GET    /euai/assessments/{id}                 — Get full assessment with checks
  PATCH  /euai/assessments/{id}/requirements/{req_id} — Update a requirement check
  POST   /euai/systems/{id}/documents/generate  — Generate compliance document
  GET    /euai/systems/{id}/documents           — List documents
  GET    /euai/documents/{id}                   — Get document content
  GET    /euai/dashboard                        — Tenant compliance overview
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.db.models.euai import (
    AiActAssessment,
    AiActDocument,
    AiActRequirementCheck,
    AiAnnexIIICategory,
    AiRiskLevel,
    AiSystem,
    AssessmentStatus,
    DocumentType,
    RegistrationStatus,
    RequirementStatus,
)
from app.db.models.user import User
from app.db.schemas.euai import (
    AiSystemCreate,
    AiSystemRead,
    AiSystemUpdate,
    AssessmentCreate,
    AssessmentRead,
    AssessmentSummary,
    ClassificationAnswers,
    ClassificationResult,
    DocumentRead,
    EuAiDashboard,
    RequirementCheckRead,
    RequirementCheckUpdate,
)
from app.db.session import get_db
from app.services.euai_risk import (
    DOCUMENT_GENERATORS,
    classify_risk,
    generate_assessment_requirements,
    update_assessment_counts,
)

router = APIRouter(prefix="/euai", tags=["EU AI Act Compliance"])

DB = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# ── Helper ────────────────────────────────────────────────────────────────────

async def _get_system_or_404(db: AsyncSession, system_id: UUID, tenant_id: str) -> AiSystem:
    result = await db.execute(
        select(AiSystem).where(
            AiSystem.id == system_id,
            AiSystem.tenant_id == tenant_id,
        )
    )
    system = result.scalar_one_or_none()
    if not system:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI system not found")
    return system


# ── AI System Registry ────────────────────────────────────────────────────────

@router.post("/systems", response_model=AiSystemRead, status_code=status.HTTP_201_CREATED)
async def register_ai_system(
    db: DB,
    current_user: CurrentUser,
    body: AiSystemCreate,
):
    """Register a new AI system in the compliance registry."""
    system = AiSystem(
        tenant_id=current_user.tenant_id,
        **body.model_dump(),
    )
    db.add(system)
    await db.commit()
    await db.refresh(system)
    return system


@router.get("/systems", response_model=list[AiSystemRead])
async def list_ai_systems(
    db: DB,
    current_user: CurrentUser,
):
    """List all AI systems registered by this tenant."""
    result = await db.execute(
        select(AiSystem)
        .where(AiSystem.tenant_id == current_user.tenant_id)
        .order_by(AiSystem.created_at.desc())
    )
    return result.scalars().all()


@router.get("/systems/{system_id}", response_model=AiSystemRead)
async def get_ai_system(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
):
    """Get a specific AI system by ID."""
    return await _get_system_or_404(db, system_id, current_user.tenant_id)


@router.patch("/systems/{system_id}", response_model=AiSystemRead)
async def update_ai_system(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
    body: AiSystemUpdate,
):
    """Update AI system metadata."""
    system = await _get_system_or_404(db, system_id, current_user.tenant_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(system, field, value)
    await db.commit()
    await db.refresh(system)
    return system


# ── Risk Classification ───────────────────────────────────────────────────────

@router.post("/systems/{system_id}/classify", response_model=ClassificationResult)
async def classify_ai_system(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
    answers: ClassificationAnswers,
):
    """
    Run risk classification on an AI system based on questionnaire answers.
    Updates the system's risk_level, annex_iii_category and registration_status.
    """
    system = await _get_system_or_404(db, system_id, current_user.tenant_id)

    result = classify_risk(system, answers)

    # Persist classification result
    system.risk_level = result.risk_level
    system.annex_iii_category = result.annex_iii_category
    system.is_gpai = answers.is_gpai
    system.gpai_systemic_risk = (
        answers.is_gpai and answers.training_compute_flops is not None and answers.training_compute_flops >= 1e25
    )
    system.classification_answers = answers.model_dump()
    system.registration_status = (
        RegistrationStatus.PENDING if result.registration_required else RegistrationStatus.NOT_REQUIRED
    )

    await db.commit()
    return result


# ── Conformity Assessments ────────────────────────────────────────────────────

@router.post(
    "/systems/{system_id}/assessments",
    response_model=AssessmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_assessment(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
    body: AssessmentCreate,
):
    """
    Start a new conformity assessment for an AI system.
    Auto-generates all requirement checks based on the assessment type.
    """
    system = await _get_system_or_404(db, system_id, current_user.tenant_id)

    if system.risk_level not in (AiRiskLevel.HIGH, AiRiskLevel.UNACCEPTABLE):
        if body.assessment_type != "fria":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Formal conformity assessments are only required for High-Risk AI systems. "
                    "Classify this system first, or use assessment_type='fria' for Fundamental Rights Impact Assessment."
                ),
            )

    assessment = AiActAssessment(
        ai_system_id=system_id,
        tenant_id=current_user.tenant_id,
        assessment_type=body.assessment_type,
        status=AssessmentStatus.DRAFT,
    )
    db.add(assessment)
    await db.flush()  # get ID before adding checks

    # Generate requirement checks
    requirements = generate_assessment_requirements(body.assessment_type)
    for req in requirements:
        check = AiActRequirementCheck(
            assessment_id=assessment.id,
            **req,
        )
        db.add(check)

    await db.commit()

    result = await db.execute(
        select(AiActAssessment)
        .where(AiActAssessment.id == assessment.id)
        .options(selectinload(AiActAssessment.requirement_checks))
    )
    return result.scalar_one()


@router.get("/systems/{system_id}/assessments", response_model=list[AssessmentSummary])
async def list_assessments(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
):
    """List all assessments for an AI system."""
    await _get_system_or_404(db, system_id, current_user.tenant_id)
    result = await db.execute(
        select(AiActAssessment)
        .where(
            AiActAssessment.ai_system_id == system_id,
            AiActAssessment.tenant_id == current_user.tenant_id,
        )
        .order_by(AiActAssessment.created_at.desc())
    )
    return result.scalars().all()


@router.get("/assessments/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(
    db: DB,
    current_user: CurrentUser,
    assessment_id: UUID,
):
    """Get a full assessment including all requirement checks."""
    result = await db.execute(
        select(AiActAssessment)
        .where(
            AiActAssessment.id == assessment_id,
            AiActAssessment.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(AiActAssessment.requirement_checks))
    )
    assessment = result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")
    return assessment


@router.patch(
    "/assessments/{assessment_id}/requirements/{requirement_id}",
    response_model=RequirementCheckRead,
)
async def update_requirement_check(
    db: DB,
    current_user: CurrentUser,
    assessment_id: UUID,
    requirement_id: UUID,
    body: RequirementCheckUpdate,
):
    """
    Update the compliance status of a single requirement check.
    Recalculates the overall assessment score after each update.
    """
    # Verify assessment belongs to tenant
    assessment_result = await db.execute(
        select(AiActAssessment)
        .where(
            AiActAssessment.id == assessment_id,
            AiActAssessment.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(AiActAssessment.requirement_checks))
    )
    assessment = assessment_result.scalar_one_or_none()
    if not assessment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assessment not found")

    # Find the specific check
    check = next((c for c in assessment.requirement_checks if c.id == requirement_id), None)
    if not check:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requirement check not found")

    # Update
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(check, field, value)

    # Recalculate score
    update_assessment_counts(assessment)

    await db.commit()
    await db.refresh(check)
    return check


# ── Document Generation ───────────────────────────────────────────────────────

@router.post(
    "/systems/{system_id}/documents/generate",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def generate_document(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
    document_type: DocumentType,
):
    """
    Generate a compliance document for an AI system.
    Supported types: technical_documentation, declaration_of_conformity, fria, qms_summary.
    """
    system = await _get_system_or_404(db, system_id, current_user.tenant_id)

    if system.risk_level is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Classify the AI system before generating documents.",
        )

    generator = DOCUMENT_GENERATORS.get(document_type)
    if not generator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Document type '{document_type.value}' generation not yet supported.",
        )

    # Mark previous versions as not current
    prev = await db.execute(
        select(AiActDocument).where(
            AiActDocument.ai_system_id == system_id,
            AiActDocument.document_type == document_type,
            AiActDocument.is_current == True,  # noqa: E712
        )
    )
    for old_doc in prev.scalars().all():
        old_doc.is_current = False

    # Get next version number
    version_result = await db.execute(
        select(func.count()).where(
            AiActDocument.ai_system_id == system_id,
            AiActDocument.document_type == document_type,
        )
    )
    version = (version_result.scalar() or 0) + 1

    type_titles = {
        DocumentType.TECHNICAL_DOCUMENTATION: "Technical Documentation (Annex IV)",
        DocumentType.DECLARATION_OF_CONFORMITY: "EU Declaration of Conformity (Art. 47)",
        DocumentType.FRIA: "Fundamental Rights Impact Assessment (Art. 27)",
        DocumentType.QMS_SUMMARY: "Quality Management System Summary (Art. 17)",
    }

    content = generator(system)
    doc = AiActDocument(
        ai_system_id=system_id,
        tenant_id=current_user.tenant_id,
        document_type=document_type,
        title=f"{system.name} — {type_titles.get(document_type, document_type.value)} v{version}",
        version=version,
        content=content,
        is_current=True,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


@router.get("/systems/{system_id}/documents", response_model=list[DocumentRead])
async def list_documents(
    db: DB,
    current_user: CurrentUser,
    system_id: UUID,
):
    """List all compliance documents for an AI system."""
    await _get_system_or_404(db, system_id, current_user.tenant_id)
    result = await db.execute(
        select(AiActDocument)
        .where(
            AiActDocument.ai_system_id == system_id,
            AiActDocument.tenant_id == current_user.tenant_id,
        )
        .order_by(AiActDocument.created_at.desc())
    )
    return result.scalars().all()


@router.get("/documents/{document_id}", response_model=DocumentRead)
async def get_document(
    db: DB,
    current_user: CurrentUser,
    document_id: UUID,
):
    """Get full content of a compliance document."""
    result = await db.execute(
        select(AiActDocument).where(
            AiActDocument.id == document_id,
            AiActDocument.tenant_id == current_user.tenant_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=EuAiDashboard)
async def get_dashboard(
    db: DB,
    current_user: CurrentUser,
):
    """Get EU AI Act compliance overview for the tenant."""
    tid = current_user.tenant_id

    # Total systems
    total_result = await db.execute(
        select(func.count()).where(AiSystem.tenant_id == tid)
    )
    total = total_result.scalar() or 0

    # By risk level
    all_systems_result = await db.execute(
        select(AiSystem).where(AiSystem.tenant_id == tid).order_by(AiSystem.created_at.desc())
    )
    all_systems = all_systems_result.scalars().all()

    by_risk: dict[str, int] = {}
    for s in all_systems:
        key = s.risk_level.value if s.risk_level else "unclassified"
        by_risk[key] = by_risk.get(key, 0) + 1

    # Systems needing assessment (High risk, no completed assessment)
    all_assessments_result = await db.execute(
        select(AiActAssessment).where(
            AiActAssessment.tenant_id == tid,
            AiActAssessment.status == AssessmentStatus.COMPLETED,
        )
    )
    assessed_system_ids = {a.ai_system_id for a in all_assessments_result.scalars().all()}
    needing_assessment = sum(
        1 for s in all_systems
        if s.risk_level == AiRiskLevel.HIGH and s.id not in assessed_system_ids
    )

    # Registered systems
    registered = sum(1 for s in all_systems if s.registration_status and s.registration_status.value == "registered")

    # Recent systems
    recent = all_systems[:5]

    # Compliance summary (average scores)
    scores_result = await db.execute(
        select(AiActAssessment.overall_score).where(
            AiActAssessment.tenant_id == tid,
            AiActAssessment.overall_score.isnot(None),
        )
    )
    scores = [s for s in scores_result.scalars().all() if s is not None]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None

    return EuAiDashboard(
        total_systems=total,
        by_risk_level=by_risk,
        systems_needing_assessment=needing_assessment,
        systems_registered=registered,
        recent_systems=recent,
        compliance_summary={
            "average_assessment_score": avg_score,
            "total_assessments_completed": len(scores),
            "high_risk_systems": by_risk.get("high", 0),
            "prohibited_systems": by_risk.get("unacceptable", 0),
        },
    )
