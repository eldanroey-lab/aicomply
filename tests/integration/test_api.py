"""
Integration tests — require a running test database.
Set TEST_DATABASE_URL env var before running.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


@pytest.mark.asyncio
async def test_mock_score():
    async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/api/v1/scoring/mock')
    assert response.status_code == 200
    data = response.json()
    assert 'compliance_score' in data
    assert data['compliance_score'] >= 0
