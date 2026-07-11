import pytest
from app.services.scoring import ScoringService, score_to_risk

service = ScoringService()

CONTROLS = [
    {'id': 'C1', 'title': 'Data Privacy', 'category': 'data_privacy', 'weight': 2.0},
    {'id': 'C2', 'title': 'Access Control', 'category': 'access_control', 'weight': 1.5},
    {'id': 'C3', 'title': 'Audit Logging', 'category': 'audit_logging', 'weight': 1.0},
]


def test_score_to_risk():
    assert score_to_risk(0.3) == 'critical'
    assert score_to_risk(0.5) == 'high'
    assert score_to_risk(0.7) == 'medium'
    assert score_to_risk(0.9) == 'low'


def test_compute_score_all_covered():
    coverage = {'C1': 'covered', 'C2': 'covered', 'C3': 'covered'}
    score, recs = service.compute_score(CONTROLS, coverage)
    assert score == 100.0
    assert recs == []


def test_compute_score_all_missing():
    coverage = {'C1': 'missing', 'C2': 'missing', 'C3': 'missing'}
    score, recs = service.compute_score(CONTROLS, coverage)
    assert score == 0.0
    assert len(recs) == 3


def test_compute_score_partial():
    coverage = {'C1': 'covered', 'C2': 'partial', 'C3': 'missing'}
    score, recs = service.compute_score(CONTROLS, coverage)
    total = 2.0 + 1.5 + 1.0
    earned = 2.0 + 0.75
    expected = round((earned / total) * 100, 1)
    assert score == expected
    assert len(recs) == 2


def test_heuristic_coverage_detects_keywords():
    doc = 'Our GDPR policy covers personal data and data subject rights.'
    coverage = service._mock_control_coverage(CONTROLS, doc)
    assert coverage.get('C1') in ('covered', 'partial')


def test_empty_controls():
    score, recs = service.compute_score([], {})
    assert score == 0.0
    assert recs
