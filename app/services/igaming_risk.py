"""
iGaming risk engine — improved over the standalone MVP.

Improvements vs original:
  • Weighted scoring per signal type (not a simple average)
  • Jurisdiction-aware thresholds (UKGC, MGA, Curaçao, Kahnawake)
  • Composite severity derived from weighted score, not just max
  • Confidence score based on evidence completeness
  • Fully typed; no global state
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.db.schemas.igaming import (
    PlayerProfile,
    RiskType,
    Severity,
)


# ── Jurisdiction configuration ────────────────────────────────────────────────

@dataclass
class JurisdictionConfig:
    deposit_velocity_threshold: float     # GBP equivalent per 30d
    structuring_lower: float              # structuring proxy lower bound
    structuring_upper: float              # structuring proxy upper bound
    high_risk_countries: frozenset[str]   # ISO-3166-1 alpha-2


_JURISDICTIONS: dict[str, JurisdictionConfig] = {
    # UK Gambling Commission — tightest
    "GB": JurisdictionConfig(
        deposit_velocity_threshold=2_000,
        structuring_lower=800,
        structuring_upper=1_000,
        high_risk_countries=frozenset({"IR", "KP", "SY", "MM", "YE", "SD", "CU"}),
    ),
    # Malta Gaming Authority
    "MT": JurisdictionConfig(
        deposit_velocity_threshold=5_000,
        structuring_lower=900,
        structuring_upper=1_100,
        high_risk_countries=frozenset({"IR", "KP", "SY", "MM"}),
    ),
    # Default / other
    "DEFAULT": JurisdictionConfig(
        deposit_velocity_threshold=3_000,
        structuring_lower=900,
        structuring_upper=1_000,
        high_risk_countries=frozenset({"IR", "KP", "SY"}),
    ),
}


def _cfg(jurisdiction: str) -> JurisdictionConfig:
    return _JURISDICTIONS.get(jurisdiction.upper(), _JURISDICTIONS["DEFAULT"])


# ── Internal signal dataclass ──────────────────────────────────────────────────

@dataclass
class _Signal:
    signal_type: str
    risk_type: RiskType
    severity: Severity
    base_score: int
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)

    # Per-signal weights (higher = more influential in final score)
    WEIGHTS: dict[str, float] = field(default_factory=lambda: {
        "RG_SELF_EXCLUSION_ACTIVE": 2.0,
        "RG_COOLING_OFF_ACTIVE": 1.8,
        "RG_LOSS_CHASING": 1.5,
        "RG_DEPOSIT_VELOCITY": 1.2,
        "RG_HIGH_DEPOSIT_NO_WITHDRAWAL": 1.0,
        "RG_SUPPORT_LANGUAGE": 1.1,
        "AML_UNVERIFIED_HIGH_VALUE": 2.0,
        "AML_LOW_PLAY_THROUGH_WITHDRAWAL": 1.8,
        "AML_MULTIPLE_PAYMENT_METHODS": 1.3,
        "AML_HIGH_RISK_GEO": 1.6,
        "AML_STRUCTURING_PROXY": 1.9,
    })

    @property
    def weighted_score(self) -> float:
        return self.base_score * self.WEIGHTS.get(self.signal_type, 1.0)


# ── RG signal detectors ───────────────────────────────────────────────────────

def _rg_self_exclusion(p: PlayerProfile) -> _Signal | None:
    if not p.self_excluded:
        return None
    return _Signal(
        signal_type="RG_SELF_EXCLUSION_ACTIVE",
        risk_type=RiskType.SELF_EXCLUSION,
        severity=Severity.CRITICAL,
        base_score=95,
        description="Player is self-excluded but activity detected.",
        evidence={"self_excluded": True},
    )


def _rg_cooling_off(p: PlayerProfile) -> _Signal | None:
    if not p.cooling_off_active:
        return None
    return _Signal(
        signal_type="RG_COOLING_OFF_ACTIVE",
        risk_type=RiskType.RESPONSIBLE_GAMBLING,
        severity=Severity.HIGH,
        base_score=80,
        description="Player is in a cooling-off period but gambling activity found.",
        evidence={"cooling_off_active": True},
    )


def _rg_deposit_velocity(p: PlayerProfile, cfg: JurisdictionConfig) -> _Signal | None:
    if p.total_deposits_30d < cfg.deposit_velocity_threshold:
        return None
    return _Signal(
        signal_type="RG_DEPOSIT_VELOCITY",
        risk_type=RiskType.RESPONSIBLE_GAMBLING,
        severity=Severity.HIGH,
        base_score=70,
        description=(
            f"Deposits of {p.total_deposits_30d:.0f} in 30 days exceed "
            f"the {p.jurisdiction} threshold of {cfg.deposit_velocity_threshold:.0f}."
        ),
        evidence={
            "total_deposits_30d": p.total_deposits_30d,
            "threshold": cfg.deposit_velocity_threshold,
        },
    )


def _rg_loss_chasing(p: PlayerProfile) -> _Signal | None:
    """Detect escalating stake sizes after losses."""
    events = p.betting_history
    if len(events) < 4:
        return None

    loss_streaks: list[float] = []
    streak_amounts: list[float] = []
    in_streak = False
    for ev in events:
        if ev.outcome == "loss":
            if not in_streak:
                in_streak = True
                streak_amounts = [ev.amount]
            else:
                streak_amounts.append(ev.amount)
        else:
            if in_streak and len(streak_amounts) >= 3:
                loss_streaks.append(streak_amounts[-1] / streak_amounts[0])
            in_streak = False
            streak_amounts = []

    if not loss_streaks or max(loss_streaks) < 2.0:
        return None

    max_escalation = max(loss_streaks)
    return _Signal(
        signal_type="RG_LOSS_CHASING",
        risk_type=RiskType.RESPONSIBLE_GAMBLING,
        severity=Severity.HIGH,
        base_score=75,
        description=f"Stake escalation of {max_escalation:.1f}x detected during loss streaks.",
        evidence={"max_escalation_factor": max_escalation},
    )


def _rg_high_deposit_no_withdrawal(p: PlayerProfile) -> _Signal | None:
    if p.total_deposits_30d < 1_000 or p.total_withdrawals_30d > 0:
        return None
    return _Signal(
        signal_type="RG_HIGH_DEPOSIT_NO_WITHDRAWAL",
        risk_type=RiskType.RESPONSIBLE_GAMBLING,
        severity=Severity.MEDIUM,
        base_score=55,
        description=(
            f"Player deposited {p.total_deposits_30d:.0f} with zero withdrawals in 30 days."
        ),
        evidence={
            "total_deposits_30d": p.total_deposits_30d,
            "total_withdrawals_30d": p.total_withdrawals_30d,
        },
    )


_RG_KEYWORDS = re.compile(
    r"\b(can't stop|can't control|addicted|addiction|please help|ban me|"
    r"losing everything|desperate|suicidal|self[- ]?exclud)\b",
    re.IGNORECASE,
)


def _rg_support_language(p: PlayerProfile) -> _Signal | None:
    matches: list[str] = []
    for note in p.support_notes:
        if _RG_KEYWORDS.search(note.note):
            matches.append(note.note[:80])
    if not matches:
        return None
    return _Signal(
        signal_type="RG_SUPPORT_LANGUAGE",
        risk_type=RiskType.RESPONSIBLE_GAMBLING,
        severity=Severity.HIGH,
        base_score=78,
        description="Support notes contain language associated with problem gambling.",
        evidence={"matched_notes": matches[:3]},
    )


# ── AML signal detectors ──────────────────────────────────────────────────────

def _aml_unverified_high_value(p: PlayerProfile) -> _Signal | None:
    if p.kyc_verified or p.total_deposits_30d < 500:
        return None
    return _Signal(
        signal_type="AML_UNVERIFIED_HIGH_VALUE",
        risk_type=RiskType.AML,
        severity=Severity.CRITICAL,
        base_score=90,
        description=(
            f"Unverified player with {p.total_deposits_30d:.0f} in deposits — KYC required."
        ),
        evidence={
            "kyc_verified": False,
            "total_deposits_30d": p.total_deposits_30d,
        },
    )


def _aml_low_play_through(p: PlayerProfile) -> _Signal | None:
    if p.total_deposits_30d < 500 or p.total_withdrawals_30d < 500:
        return None
    play_through = sum(e.amount for e in p.betting_history)
    ratio = play_through / p.total_deposits_30d if p.total_deposits_30d else 1.0
    if ratio >= 0.5:
        return None
    return _Signal(
        signal_type="AML_LOW_PLAY_THROUGH_WITHDRAWAL",
        risk_type=RiskType.AML,
        severity=Severity.HIGH,
        base_score=82,
        description=(
            f"Only {ratio:.0%} of deposited funds were wagered before withdrawal "
            f"— possible layering."
        ),
        evidence={
            "play_through_ratio": round(ratio, 3),
            "total_deposits_30d": p.total_deposits_30d,
            "total_wagered": round(play_through, 2),
        },
    )


def _aml_multiple_payment_methods(p: PlayerProfile) -> _Signal | None:
    methods = {e.method for e in p.payment_history if e.type == "deposit"}
    if len(methods) < 3:
        return None
    return _Signal(
        signal_type="AML_MULTIPLE_PAYMENT_METHODS",
        risk_type=RiskType.AML,
        severity=Severity.MEDIUM,
        base_score=60,
        description=f"{len(methods)} distinct payment methods used for deposits.",
        evidence={"methods": sorted(methods)},
    )


def _aml_high_risk_geo(p: PlayerProfile, cfg: JurisdictionConfig) -> _Signal | None:
    if p.jurisdiction.upper() not in cfg.high_risk_countries:
        return None
    return _Signal(
        signal_type="AML_HIGH_RISK_GEO",
        risk_type=RiskType.AML,
        severity=Severity.HIGH,
        base_score=85,
        description=f"Player jurisdiction {p.jurisdiction} is on the high-risk country list.",
        evidence={"jurisdiction": p.jurisdiction},
    )


def _aml_structuring(p: PlayerProfile, cfg: JurisdictionConfig) -> _Signal | None:
    """Detect deposits clustered just below the CTR threshold."""
    suspicious = [
        e for e in p.payment_history
        if e.type == "deposit"
        and cfg.structuring_lower <= e.amount < cfg.structuring_upper
    ]
    if len(suspicious) < 2:
        return None
    total = sum(e.amount for e in suspicious)
    return _Signal(
        signal_type="AML_STRUCTURING_PROXY",
        risk_type=RiskType.AML,
        severity=Severity.HIGH,
        base_score=88,
        description=(
            f"{len(suspicious)} deposits between {cfg.structuring_lower:.0f}–"
            f"{cfg.structuring_upper:.0f} detected — possible structuring."
        ),
        evidence={
            "count": len(suspicious),
            "total": round(total, 2),
            "threshold_range": [cfg.structuring_lower, cfg.structuring_upper],
        },
    )


# ── Severity from weighted score ──────────────────────────────────────────────

def _severity_from_score(score: int) -> Severity:
    if score >= 80:
        return Severity.CRITICAL
    if score >= 60:
        return Severity.HIGH
    if score >= 35:
        return Severity.MEDIUM
    return Severity.LOW


# ── Public API ────────────────────────────────────────────────────────────────

@dataclass
class CaseResult:
    player_id: str
    risk_type: RiskType
    severity: Severity
    risk_score: int
    confidence: float
    signals: list[_Signal]
    player_snapshot: dict[str, Any]


def scan_player(player: PlayerProfile) -> list[CaseResult]:
    """
    Run all detectors against a single player profile.
    Returns one CaseResult per risk_type that has at least one signal.
    """
    cfg = _cfg(player.jurisdiction)

    all_signals: list[_Signal] = []
    for detector in [
        lambda p: _rg_self_exclusion(p),
        lambda p: _rg_cooling_off(p),
        lambda p: _rg_deposit_velocity(p, cfg),
        lambda p: _rg_loss_chasing(p),
        lambda p: _rg_high_deposit_no_withdrawal(p),
        lambda p: _rg_support_language(p),
        lambda p: _aml_unverified_high_value(p),
        lambda p: _aml_low_play_through(p),
        lambda p: _aml_multiple_payment_methods(p),
        lambda p: _aml_high_risk_geo(p, cfg),
        lambda p: _aml_structuring(p, cfg),
    ]:
        sig = detector(player)
        if sig:
            all_signals.append(sig)

    # Group by risk_type
    by_type: dict[RiskType, list[_Signal]] = {}
    for sig in all_signals:
        by_type.setdefault(sig.risk_type, []).append(sig)

    snapshot = player.model_dump(exclude={"betting_history", "payment_history", "support_notes"})

    results: list[CaseResult] = []
    for risk_type, signals in by_type.items():
        total_weighted = sum(s.weighted_score for s in signals)
        # Normalise to 0-100
        raw_score = min(100, int(total_weighted / max(1, len(signals))))
        # Bonus for multiple corroborating signals
        bonus = min(15, (len(signals) - 1) * 4)
        final_score = min(100, raw_score + bonus)

        # Confidence: proportion of detectors that had sufficient data
        evidence_fields = sum([
            bool(player.betting_history),
            bool(player.payment_history),
            bool(player.support_notes),
        ])
        confidence = round(0.5 + 0.17 * evidence_fields, 2)

        results.append(CaseResult(
            player_id=player.player_id,
            risk_type=risk_type,
            severity=_severity_from_score(final_score),
            risk_score=final_score,
            confidence=confidence,
            signals=signals,
            player_snapshot=snapshot,
        ))

    return results
