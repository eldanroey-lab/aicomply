"""
SQLAlchemy models for iGaming compliance monitoring.
Stores persistent ComplianceCases and their constituent RiskSignals,
scoped per tenant for multi-tenant isolation.
"""
from __future__ import annotations

import enum
from sqlalchemy import String, Integer, Float, ForeignKey, JSON, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class RiskTypeEnum(str, enum.Enum):
    RESPONSIBLE_GAMBLING = "RESPONSIBLE_GAMBLING"
    AML = "AML"
    FRAUD = "FRAUD"
    SELF_EXCLUSION = "SELF_EXCLUSION"


class SeverityEnum(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatusEnum(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class IgamingRiskSignal(Base):
    __tablename__ = "igaming_risk_signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[int] = mapped_column(ForeignKey("igaming_compliance_cases.id", ondelete="CASCADE"))
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    risk_type: Mapped[RiskTypeEnum] = mapped_column(SAEnum(RiskTypeEnum), nullable=False)
    severity: Mapped[SeverityEnum] = mapped_column(SAEnum(SeverityEnum), nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict | None] = mapped_column(JSON)

    case: Mapped["IgamingComplianceCase"] = relationship(back_populates="signals")


class IgamingComplianceCase(Base):
    __tablename__ = "igaming_compliance_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Player context
    player_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(50))

    # Risk classification
    risk_type: Mapped[RiskTypeEnum] = mapped_column(SAEnum(RiskTypeEnum), nullable=False)
    severity: Mapped[SeverityEnum] = mapped_column(SAEnum(SeverityEnum), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Case management
    status: Mapped[CaseStatusEnum] = mapped_column(
        SAEnum(CaseStatusEnum), default=CaseStatusEnum.OPEN, nullable=False
    )
    assigned_to: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    # Snapshot of the input data that triggered this case
    player_snapshot: Mapped[dict | None] = mapped_column(JSON)

    signals: Mapped[list["IgamingRiskSignal"]] = relationship(
        back_populates="case", cascade="all, delete-orphan"
    )
