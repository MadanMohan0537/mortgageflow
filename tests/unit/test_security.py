"""Auth helper unit tests."""

import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import create_access_token, decode_access_token


def test_jwt_round_trip():
    settings = Settings(jwt_secret="unit-secret", jwt_algorithm="HS256")
    token = create_access_token("reviewer-42", settings=settings)
    assert decode_access_token(token, settings=settings) == "reviewer-42"


def test_jwt_invalid_raises():
    settings = Settings(jwt_secret="unit-secret")
    with pytest.raises(HTTPException) as exc:
        decode_access_token("not-a-token", settings=settings)
    assert exc.value.status_code == 401
