"""
iGaming compliance API endpoints.

All routes require JWT authentication. Data is scoped to the caller's tenant_id
so operators never see each other's player data.

Endpoints:
  POST /igaming/scan          — JSON body with player profiles
  POST /igaming/scan-csv      — CSV upload (one player row per line)
  GET  /igaming/cases         — List cases for this tenant
  GET  /igaming/cases/{id}    — Single case with signals
  PATCH /igaming/cases/{id}   — Update status / assignee / notes
"""
from __future__ import annotations

import csv
import io
import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_current_user
from app.db.models.igaming import IgamingComplianceCase, IgamingRiskSignal
from app.db.models.user import User
from app.db.schemas.igaming import (
    CaseStatus,
    CaseUpdate,
    ComplianceCaseRead,
    PlayerProfile,
    ScanRequest,
    ScanResponse,
    ScanSummary,
    Severity,
)
from app.db.session import get_db
from app.services.igaming_risk import scan_player

router = APIRouter(prefix="/igaming", tags=["iGaming Compliance"])

CurrentUser = Annotated[User, Depends(get_current_user)]
DB = Annotated[AsyncSession, Depends(get_db)]


# ── helpers ───────────────────────────────────────────────────────────────────

_SEVERITY_ORDER = {
    Severity.LOW: 0,
    Severity.MEDIUM: 1,
    Severity.HIGH: 2,
    Severity.CRITICAL: 3,
}


async def _persist_cases(
    db: AsyncSession,
    tenant_id: int,
    players: list[PlayerProfile],
) -> list[IgamingComplianceCase]:
    """Run the risk engine over each player and persist the resulting cases."""
    created: list[IgamingComplianceCase] = []
    for player in players:
        case_results = scan_player(player)
        for cr in case_results:
            case = IgamingComplianceCase(
                tenant_id=tenant_id,
                player_id=cr.player_id,
                jurisdiction=player.jurisdiction,
                risk_type=cr.risk_type,
                severity=cr.severity,
                risk_score=cr.risk_score,
                confidence=cr.confidence,
                status=CaseStatus.OPEN,
                player_snapshot=cr.player_snapshot,
            )
            db.add(case)
            await db.flush()  # get case.id

            for sig in cr.signals:
                db.add(IgamingRiskSignal(
                    case_id=case.id,
                    tenant_id=tenant_id,
                    signal_type=sig.signal_type,
                    risk_type=sig.risk_type,
                    severity=sig.severity,
                    score=sig.base_score,
                    description=sig.description,
                    evidence=sig.evidence,
                ))

            await db.refresh(case)
            created.append(case)

    await db.commit()
    return created


def _build_summaries(
    players: list[PlayerProfile],
    cases: list[IgamingComplianceCase],
) -> list[ScanSummary]:
    summaries: list[ScanSummary] = []
    # index cases by player_id
    by_player: dict[str, list[IgamingComplianceCase]] = {}
    for c in cases:
        by_player.setdefault(c.player_id, []).append(c)

    all_player_ids = {p.player_id for p in players}
    for pid in all_player_ids:
        player_cases = by_player.get(pid, [])
        highest = max(
            (c.severity for c in player_cases),
            key=lambda s: _SEVERITY_ORDER[s],
            default=None,
        )
        summaries.append(ScanSummary(
            player_id=pid,
            cases_created=len(player_cases),
            highest_severity=highest,
            risk_scores={c.risk_type.value: c.risk_score for c in player_cases},
        ))
    return summaries


# ── POST /igaming/scan ────────────────────────────────────────────────────────

@router.post("/scan", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def scan_players(
    body: ScanRequest,
    db: DB,
    current_user: CurrentUser,
):
    """
    Submit one or more player profiles for compliance scanning.
    Risk signals are evaluated and ComplianceCases created for any detected issues.
    """
    if not body.players:
        raise HTTPException(status_code=400, detail="No players provided.")
    if len(body.players) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 players per request.")

    cases = await _persist_cases(db, current_user.tenant_id, body.players)
    summaries = _build_summaries(body.players, cases)

    return ScanResponse(
        total_players=len(body.players),
        total_cases=len(cases),
        summaries=summaries,
    )


# ── POST /igaming/scan-csv ────────────────────────────────────────────────────

@router.post("/scan-csv", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def scan_players_csv(
    file: UploadFile = File(...),
    db: DB,
    current_user: CurrentUser,
):
    """
    Upload a CSV file to scan multiple players at once.

    Expected columns (all optional except player_id):
      player_id, jurisdiction, self_excluded, cooling_off_active,
      total_deposits_30d, total_withdrawals_30d, deposit_count_30d, kyc_verified
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted.")

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")  # handle BOM
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")

    reader = csv.DictReader(io.StringIO(text))
    players: list[PlayerProfile] = []
    errors: list[str] = []

    for i, row in enumerate(reader, start=2):  # row 1 = header
        pid = row.get("player_id", "").strip()
        if not pid:
            errors.append(f"Row {i}: missing player_id")
            continue
        try:
            players.append(PlayerProfile(
                player_id=pid,
                jurisdiction=row.get("jurisdiction", "GB").strip() or "GB",
                self_excluded=row.get("self_excluded", "false").lower() in ("1", "true", "yes"),
                cooling_off_active=row.get("cooling_off_active", "false").lower() in ("1", "true", "yes"),
                total_deposits_30d=float(row.get("total_deposits_30d") or 0),
                total_withdrawals_30d=float(row.get("total_withdrawals_30d") or 0),
                deposit_count_30d=int(float(row.get("deposit_count_30d") or 0)),
                kyc_verified=row.get("kyc_verified", "true").lower() not in ("0", "false", "no"),
            ))
        except (ValueError, TypeError) as exc:
            errors.append(f"Row {i}: {exc}")

    if not players and errors:
        raise HTTPException(status_code=422, detail="; ".join(errors[:10]))
    if len(players) > 500:
        raise HTTPException(status_code=400, detail="Maximum 500 players per CSV upload.")

    cases = await _persist_cases(db, current_user.tenant_id, players)
    summaries = _build_summaries(players, cases)

    return ScanResponse(
        total_players=len(players),
        total_cases=len(cases),
        summaries=summaries,
    )


# ── GET /igaming/cases ────────────────────────────────────────────────────────

@router.get("/cases", response_model=list[ComplianceCaseRead])
async def list_cases(
    db: DB,
    current_user: CurrentUser,
    status_filter: CaseStatus | None = Query(None, alias="status"),
    risk_type: str | None = None,
    player_id: str | None = None,
    skip: int = 0,
    limit: int = Query(50, le=200),
):
    """List compliance cases for the current tenant, with optional filters."""
    q = (
        select(IgamingComplianceCase)
        .options(selectinload(IgamingComplianceCase.signals))
        .where(IgamingComplianceCase.tenant_id == current_user.tenant_id)
    )
    if status_filter:
        q = q.where(IgamingComplianceCase.status == status_filter)
    if risk_type:
        q = q.where(IgamingComplianceCase.risk_type == risk_type)
    if player_id:
        q = q.where(IgamingComplianceCase.player_id == player_id)

    q = q.order_by(IgamingComplianceCase.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


# ── GET /igaming/cases/{case_id} ──────────────────────────────────────────────

@router.get("/cases/{case_id}", response_model=ComplianceCaseRead)
async def get_case(
    case_id: int,
    db: DB,
    current_user: CurrentUser,
):
    result = await db.execute(
        select(IgamingComplianceCase)
        .options(selectinload(IgamingComplianceCase.signals))
        .where(
            IgamingComplianceCase.id == case_id,
            IgamingComplianceCase.tenant_id == current_user.tenant_id,
        )
    )
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    return case


# ── PATCH /igaming/cases/{case_id} ───────────────────────────────────────────

@router.patch("/cases/{case_id}", response_model=ComplianceCaseRead)
async def update_case(
    case_id: int,
    body: CaseUpdate,
    db: DB,
    current_user: CurrentUser,
):
    """Update a case's status, assignee, or compliance notes."""
    result = await db.execute(
        select(IgamingComplianceCase)
        .options(selectinload(IgamingComplianceCase.signals))
        .where(
            IgamingComplianceCase.id == case_id,
            IgamingComplianceCase.tenant_id == current_user.tenant_id,
        )
    )
    case = result.scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")

    if body.status is not None:
        case.status = body.status
    if body.assigned_to is not None:
        case.assigned_to = body.assigned_to
    if body.notes is not None:
        case.notes = body.notes

    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case
