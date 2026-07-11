"""
Compliance scoring engine.
Each framework has a list of controls with weights.
Documents are scored by AI analysis; controls are marked covered/partial/missing.
The tenant score is a weighted average across all frameworks.
"""
import logging
from dataclasses import dataclass
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.document import Document
from app.db.models.framework import Framework

logger = logging.getLogger(__name__)

RISK_THRESHOLDS = {
    'critical': (0.0, 0.4),
    'high':     (0.4, 0.6),
    'medium':   (0.6, 0.8),
    'low':      (0.8, 1.01),
}


def score_to_risk(score: float) -> str:
    for level, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score < hi:
            return level
    return 'low'


@dataclass
class ScoringResult:
    score: float            # 0-100
    risk_level: str
    coverage: dict          # control_id -> 'covered' | 'partial' | 'missing'
    recommendations: list[str]


class ScoringService:
    def _mock_control_coverage(self, controls: list[dict], doc_text: str) -> dict:
        """
        Heuristic scoring when no AI key is configured.
        Real implementation calls document_ai service.
        """
        keywords_map = {
            'data_privacy': ['gdpr', 'privacy', 'personal data', 'data subject'],
            'access_control': ['access', 'rbac', 'permission', 'authentication', 'mfa'],
            'incident_response': ['incident', 'breach', 'response plan', 'notification'],
            'audit_logging': ['audit', 'log', 'monitoring', 'trail'],
            'encryption': ['encrypt', 'tls', 'aes', 'at-rest', 'in-transit'],
        }
        coverage = {}
        doc_lower = doc_text.lower()
        for ctrl in controls:
            ctrl_id = ctrl.get('id', '')
            category = ctrl.get('category', '').lower()
            keywords = keywords_map.get(category, [ctrl.get('title', '').lower()])
            hits = sum(1 for kw in keywords if kw in doc_lower)
            if hits >= 2:
                coverage[ctrl_id] = 'covered'
            elif hits == 1:
                coverage[ctrl_id] = 'partial'
            else:
                coverage[ctrl_id] = 'missing'
        return coverage

    def compute_score(
        self, controls: list[dict], coverage: dict
    ) -> tuple[float, list[str]]:
        if not controls:
            return 0.0, ['No controls defined in framework']

        total_weight = sum(c.get('weight', 1.0) for c in controls)
        earned = 0.0
        recommendations = []

        for ctrl in controls:
            ctrl_id = ctrl['id']
            weight = ctrl.get('weight', 1.0)
            status = coverage.get(ctrl_id, 'missing')
            if status == 'covered':
                earned += weight
            elif status == 'partial':
                earned += weight * 0.5
                recommendations.append(
                    f"Partially covered control '{ctrl['title']}' — provide more evidence."
                )
            else:
                recommendations.append(
                    f"Missing control '{ctrl['title']}' — no documentation found."
                )

        score = round((earned / total_weight) * 100, 1) if total_weight > 0 else 0.0
        return score, recommendations

    async def score_document(
        self, db: AsyncSession, document: Document, framework: Optional[Framework] = None
    ) -> ScoringResult:
        """Score a single document against its linked framework."""
        if not framework and document.framework_id:
            result = await db.execute(
                select(Framework).where(Framework.id == document.framework_id)
            )
            framework = result.scalars().first()

        controls = (framework.controls or []) if framework else []
        doc_text = document.ai_summary or document.original_name

        coverage = self._mock_control_coverage(controls, doc_text)
        score_pct, recs = self.compute_score(controls, coverage)
        risk = score_to_risk(score_pct / 100)

        return ScoringResult(
            score=score_pct,
            risk_level=risk,
            coverage=coverage,
            recommendations=recs,
        )

    async def refresh_all_tenant_scores(self, db: AsyncSession):
        """Recompute and persist framework-level compliance scores."""
        result = await db.execute(select(Framework))
        frameworks = result.scalars().all()
        for fw in frameworks:
            docs_result = await db.execute(
                select(Document).where(
                    Document.framework_id == fw.id,
                    Document.compliance_score.is_not(None),
                )
            )
            docs = docs_result.scalars().all()
            if docs:
                fw.compliance_score = round(
                    sum(d.compliance_score for d in docs) / len(docs), 1
                )
                db.add(fw)
        await db.commit()
        logger.info(f'Refreshed scores for {len(frameworks)} frameworks')


scoring_service = ScoringService()
