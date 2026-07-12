"""Pydantic schemas for the EU AI Act compliance module."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.euai import (
    AiAnnexIIICategory,
    AiRiskLevel,
    AiSystemRole,
    AiSystemStatus,
    AssessmentStatus,
    DocumentType,
    RegistrationStatus,
    RequirementStatus,
)


# ── AI System ─────────────────────────────────────────────────────────────────

class AiSystemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field("1.0", max_length=50)
    description: Optional[str] = None
    intended_purpose: str = Field(..., min_length=10)
    provider_name: Optional[str] = None
    role: AiSystemRole = AiSystemRole.PROVIDER
    eu_market: bool = True
    affects_natural_persons: bool = True
    is_gpai: bool = False
    gpai_systemic_risk: bool = False
    is_safety_component: bool = False
    deployment_sectors: list[str] = Field(default_factory=list)


class AiSystemUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    intended_purpose: Optional[str] = None
    provider_name: Optional[str] = None
    role: Optional[AiSystemRole] = None
    eu_market: Optional[bool] = None
    affects_natural_persons: Optional[bool] = None
    is_gpai: Optional[bool] = None
    gpai_systemic_risk: Optional[bool] = None
    is_safety_component: Optional[bool] = None
    deployment_sectors: Optional[list[str]] = None
    eu_database_id: Optional[str] = None
    registration_status: Optional[RegistrationStatus] = None
    status: Optional[AiSystemStatus] = None


class AiSystemRead(BaseModel):
    id: UUID
    tenant_id: str
    name: str
    version: str
    description: Optional[str]
    intended_purpose: str
    provider_name: Optional[str]
    role: AiSystemRole
    risk_level: Optional[AiRiskLevel]
    annex_iii_category: Optional[AiAnnexIIICategory]
    eu_market: bool
    affects_natural_persons: bool
    is_gpai: bool
    gpai_systemic_risk: bool
    is_safety_component: bool
    deployment_sectors: list[str]
    registration_status: RegistrationStatus
    eu_database_id: Optional[str]
    status: AiSystemStatus
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ── Classification ────────────────────────────────────────────────────────────

class ClassificationAnswers(BaseModel):
    """
    Questionnaire answers used to classify an AI system's risk level.
    Each field corresponds to a key criterion from the EU AI Act.
    """
    # Annex III category questions
    uses_biometrics: bool = False
    biometric_purpose: Optional[str] = None          # "remote_id", "categorisation", "emotion"

    is_critical_infrastructure: bool = False

    education_purpose: Optional[str] = None          # "admission", "evaluation", "monitoring"

    employment_purpose: Optional[str] = None          # "recruitment", "performance", "termination"

    essential_service_purpose: Optional[str] = None  # "benefits", "credit", "insurance", "emergency"

    law_enforcement_use: bool = False
    migration_use: bool = False
    justice_use: bool = False
    electoral_influence: bool = False

    # Article 5 prohibited use checks
    social_scoring_by_public: bool = False
    real_time_remote_biometric_public: bool = False
    subliminal_manipulation: bool = False
    exploits_vulnerability: bool = False

    # Limited risk (Art. 50 transparency)
    is_chatbot: bool = False
    generates_deepfakes: bool = False
    emotion_recognition_limited: bool = False

    # GPAI
    is_gpai: bool = False
    training_compute_flops: Optional[float] = None    # for systemic risk designation


class ClassificationResult(BaseModel):
    risk_level: AiRiskLevel
    annex_iii_category: AiAnnexIIICategory
    is_prohibited: bool
    prohibition_reason: Optional[str]
    key_obligations: list[str]
    registration_required: bool
    summary: str


# ── Assessment ────────────────────────────────────────────────────────────────

class RequirementCheckUpdate(BaseModel):
    status: RequirementStatus
    evidence: Optional[str] = None
    notes: Optional[str] = None
    action_required: Optional[str] = None


class RequirementCheckRead(BaseModel):
    id: UUID
    assessment_id: UUID
    sort_order: int
    article: str
    article_title: str
    requirement_text: str
    guidance: Optional[str]
    status: RequirementStatus
    evidence: Optional[str]
    notes: Optional[str]
    action_required: Optional[str]

    model_config = {"from_attributes": True}


class AssessmentCreate(BaseModel):
    assessment_type: str = Field("provider", pattern="^(provider|deployer|fria)$")


class AssessmentRead(BaseModel):
    id: UUID
    ai_system_id: UUID
    tenant_id: str
    assessment_type: str
    status: AssessmentStatus
    overall_score: Optional[float]
    compliant_count: int
    partial_count: int
    non_compliant_count: int
    not_applicable_count: int
    assessor_notes: Optional[str]
    completed_at: Optional[datetime]
    created_at: datetime
    requirement_checks: list[RequirementCheckRead] = []

    model_config = {"from_attributes": True}


class AssessmentSummary(BaseModel):
    id: UUID
    ai_system_id: UUID
    assessment_type: str
    status: AssessmentStatus
    overall_score: Optional[float]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Documents ─────────────────────────────────────────────────────────────────

class DocumentRead(BaseModel):
    id: UUID
    ai_system_id: UUID
    document_type: DocumentType
    title: str
    version: int
    content: dict[str, Any]
    is_current: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Dashboard ─────────────────────────────────────────────────────────────────

class EuAiDashboard(BaseModel):
    total_systems: int
    by_risk_level: dict[str, int]
    systems_needing_assessment: int
    systems_registered: int
    recent_systems: list[AiSystemRead]
    compliance_summary: dict[str, Any]
