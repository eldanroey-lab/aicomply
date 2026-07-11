"""
Pydantic schemas for iGaming compliance endpoints.
"""
from __future__ import annotations

import enum
from typing import Any
from pydantic import BaseModel, Field
from datetime import datetime


# ── Enums ────────────────────────────────────────────────────────────────────

class RiskType(str, enum.Enum):
    RESPONSIBLE_GAMBLING = "RESPONSIBLE_GAMBLING"
    AML = "AML"
    FRAUD = "FRAUD"
    SELF_EXCLUSION = "SELF_EXCLUSION"


class Severity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# ── Input models (player data for a scan) ────────────────────────────────────

class BettingEvent(BaseModel):
    timestamp: str
    amount: float
    game_type: str
    outcome: str                         # win / loss
    session_duration_minutes: float = 0


class PaymentEvent(BaseModel):
    timestamp: str
    type: str                            # deposit / withdrawal
    amount: float
    method: str
    currency: str = "GBP"


class SupportNote(BaseModel):
    timestamp: str
    category: str
    note: str


class PlayerProfile(BaseModel):
    player_id: str
    jurisdiction: str = "GB"            # ISO-3166 country code

    # Behavioural flags
    self_excluded: bool = False
    cooling_off_active: bool = False

    # Aggregated deposit / withdrawal stats (last 30 days unless noted)
    total_deposits_30d: float = 0
    total_withdrawals_30d: float = 0
    deposit_count_30d: int = 0

    # Unverified status
    kyc_verified: bool = True

    # Event history (optional — detailed signals require these)
    betting_history: list[BettingEvent] = Field(default_factory=list)
    payment_history: list[PaymentEvent] = Field(default_factory=list)
    support_notes: list[SupportNote] = Field(default_factory=list)


class ScanRequest(BaseModel):
    players: list[PlayerProfile]


# ── Output models ─────────────────────────────────────────────────────────────

class RiskSignalRead(BaseModel):
    id: int
    signal_type: str
    risk_type: RiskType
    severity: Severity
    score: int
    description: str
    evidence: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ComplianceCaseRead(BaseModel):
    id: int
    tenant_id: int
    player_id: str
    jurisdiction: str | None
    risk_type: RiskType
    severity: Severity
    risk_score: int
    confidence: float
    status: CaseStatus
    assigned_to: str | None
    notes: str | None
    signals: list[RiskSignalRead] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScanSummary(BaseModel):
    """Lightweight scan result returned from POST /igaming/scan."""
    player_id: str
    cases_created: int
    highest_severity: Severity | None
    risk_scores: dict[str, int]          # risk_type → score


class ScanResponse(BaseModel):
    total_players: int
    total_cases: int
    summaries: list[ScanSummary]


# ── Case management ───────────────────────────────────────────────────────────

class CaseUpdate(BaseModel):
    status: CaseStatus | None = None
    assigned_to: str | None = None
    notes: str | None = None
