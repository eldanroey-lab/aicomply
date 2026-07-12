"""
EU AI Act compliance models.

Covers:
  - AI System registry (provider + deployer roles)
  - Risk classification (Unacceptable / High / Limited / Minimal)
  - Conformity assessments (Articles 9-20 for providers, 26-27 for deployers)
  - Technical documentation generation (Annex IV)
  - FRIA - Fundamental Rights Impact Assessment (Article 27)
"""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, Enum, Float, ForeignKey,
    Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base import Base


# ── Enumerations ──────────────────────────────────────────────────────────────

class AiRiskLevel(str, enum.Enum):
    UNACCEPTABLE = "unacceptable"   # Art. 5 — prohibited, must not be placed on market
    HIGH = "high"                    # Annex III or safety-component product
    LIMITED = "limited"              # Transparency obligations only (Art. 50)
    MINIMAL = "minimal"              # No specific obligations


class AiSystemRole(str, enum.Enum):
    PROVIDER = "provider"            # Develops / places on market
    DEPLOYER = "deployer"            # Uses in professional context
    BOTH = "both"                    # Acts as both


class AiAnnexIIICategory(str, enum.Enum):
    BIOMETRICS = "biometrics"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"
    EDUCATION = "education"
    EMPLOYMENT = "employment"
    ESSENTIAL_SERVICES = "essential_services"
    LAW_ENFORCEMENT = "law_enforcement"
    MIGRATION = "migration"
    JUSTICE_DEMOCRACY = "justice_democracy"
    NONE = "none"


class AiSystemStatus(str, enum.Enum):
    ACTIVE = "active"
    UNDER_REVIEW = "under_review"
    ARCHIVED = "archived"


class AssessmentStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    SUBMITTED = "submitted"


class RequirementStatus(str, enum.Enum):
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


class DocumentType(str, enum.Enum):
    TECHNICAL_DOCUMENTATION = "technical_documentation"   # Annex IV
    DECLARATION_OF_CONFORMITY = "declaration_of_conformity"  # Art. 47
    FRIA = "fria"                                          # Art. 27 deployer
    QMS_SUMMARY = "qms_summary"                            # Art. 17


class RegistrationStatus(str, enum.Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    REGISTERED = "registered"


# ── Models ────────────────────────────────────────────────────────────────────

class AiSystem(Base):
    """Registry of AI systems subject to EU AI Act obligations."""
    __tablename__ = "euai_systems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Identity
    name = Column(String(255), nullable=False)
    version = Column(String(50), nullable=False, default="1.0")
    description = Column(Text, nullable=True)
    intended_purpose = Column(Text, nullable=False)
    provider_name = Column(String(255), nullable=True)   # if deployer: who built it

    # Role & classification
    role = Column(Enum(AiSystemRole), nullable=False, default=AiSystemRole.PROVIDER)
    risk_level = Column(Enum(AiRiskLevel), nullable=True)
    annex_iii_category = Column(Enum(AiAnnexIIICategory), nullable=True, default=AiAnnexIIICategory.NONE)

    # Scope flags (used by risk classifier)
    eu_market = Column(Boolean, default=True)            # Deployed in EU?
    affects_natural_persons = Column(Boolean, default=True)
    is_gpai = Column(Boolean, default=False)             # General Purpose AI model?
    gpai_systemic_risk = Column(Boolean, default=False)  # >10^25 FLOPs or designated?
    is_safety_component = Column(Boolean, default=False)  # Safety component in regulated product?
    deployment_sectors = Column(JSON, default=list)       # List of sector strings

    # Classification questionnaire answers (stored for audit)
    classification_answers = Column(JSON, default=dict)

    # Registration (Art. 49 — EU database)
    registration_status = Column(
        Enum(RegistrationStatus),
        default=RegistrationStatus.NOT_REQUIRED,
    )
    eu_database_id = Column(String(100), nullable=True)

    status = Column(Enum(AiSystemStatus), default=AiSystemStatus.ACTIVE)

    # Relationships
    assessments = relationship("AiActAssessment", back_populates="ai_system", cascade="all, delete-orphan")
    documents = relationship("AiActDocument", back_populates="ai_system", cascade="all, delete-orphan")


class AiActAssessment(Base):
    """Conformity assessment of an AI system against EU AI Act requirements."""
    __tablename__ = "euai_assessments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ai_system_id = Column(UUID(as_uuid=True), ForeignKey("euai_systems.id"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Type: full provider assessment, deployer assessment, or FRIA only
    assessment_type = Column(String(50), nullable=False, default="provider")  # provider|deployer|fria

    status = Column(Enum(AssessmentStatus), default=AssessmentStatus.DRAFT)

    # Scores
    overall_score = Column(Float, nullable=True)          # 0-100
    compliant_count = Column(Integer, default=0)
    partial_count = Column(Integer, default=0)
    non_compliant_count = Column(Integer, default=0)
    not_applicable_count = Column(Integer, default=0)

    assessor_notes = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    ai_system = relationship("AiSystem", back_populates="assessments")
    requirement_checks = relationship(
        "AiActRequirementCheck",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="AiActRequirementCheck.sort_order",
    )


class AiActRequirementCheck(Base):
    """
    Individual requirement check within a conformity assessment.
    Maps to a specific Article or sub-requirement of the EU AI Act.
    """
    __tablename__ = "euai_requirement_checks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assessment_id = Column(UUID(as_uuid=True), ForeignKey("euai_assessments.id"), nullable=False)
    sort_order = Column(Integer, default=0)

    # Requirement identity
    article = Column(String(20), nullable=False)          # e.g. "Art. 9"
    article_title = Column(String(200), nullable=False)
    requirement_text = Column(Text, nullable=False)       # What the law requires
    guidance = Column(Text, nullable=True)                # Practical guidance

    # Assessment result
    status = Column(Enum(RequirementStatus), default=RequirementStatus.PENDING)
    evidence = Column(Text, nullable=True)                # User-provided evidence
    notes = Column(Text, nullable=True)
    action_required = Column(Text, nullable=True)         # Remediation step if non-compliant

    assessment = relationship("AiActAssessment", back_populates="requirement_checks")


class AiActDocument(Base):
    """
    Generated compliance document (Technical Documentation, DoC, FRIA, etc.).
    """
    __tablename__ = "euai_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ai_system_id = Column(UUID(as_uuid=True), ForeignKey("euai_systems.id"), nullable=False)
    tenant_id = Column(String, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    document_type = Column(Enum(DocumentType), nullable=False)
    title = Column(String(255), nullable=False)
    version = Column(Integer, default=1)
    content = Column(JSON, nullable=False, default=dict)   # Structured document content
    is_current = Column(Boolean, default=True)

    ai_system = relationship("AiSystem", back_populates="documents")
