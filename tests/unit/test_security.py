import pytest
from app.core.security import hash_password, verify_password, create_access_token, decode_token


def test_password_hashing():
    hashed = hash_password('supersecret')
    assert verify_password('supersecret', hashed)
    assert not verify_password('wrong', hashed)


def test_access_token_roundtrip():
    token = create_access_token(subject=42)
    payload = decode_token(token)
    assert payload['sub'] == '42'
    assert payload['type'] == 'access'


def test_invalid_token_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        decode_token('not.a.valid.token')
