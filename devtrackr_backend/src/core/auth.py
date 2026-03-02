from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.core.settings import get_settings
from src.models.models import OrgMembership, User


@dataclass(frozen=True)
class AuthContext:
    """Resolved authentication context for the current request."""

    user: User
    active_org_id: Optional[uuid.UUID]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict) -> str:
    settings = get_settings()
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")


# PUBLIC_INTERFACE
def create_access_token(user_id: uuid.UUID) -> str:
    """Create a short-lived access JWT."""
    settings = get_settings()
    now = _utcnow()
    payload = {
        "sub": str(user_id),
        "typ": "access",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.access_token_ttl_minutes)).timestamp()),
    }
    return _encode(payload)


# PUBLIC_INTERFACE
def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a longer-lived refresh JWT."""
    settings = get_settings()
    now = _utcnow()
    payload = {
        "sub": str(user_id),
        "typ": "refresh",
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.refresh_token_ttl_days)).timestamp()),
    }
    return _encode(payload)


def _get_user(db: Session, user_id: uuid.UUID) -> User:
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive")
    return user


# PUBLIC_INTERFACE
def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    access_token: Optional[str] = Cookie(default=None, alias="devtrackr_access"),
    active_org: Optional[str] = Cookie(default=None, alias="devtrackr_active_org"),
) -> AuthContext:
    """FastAPI dependency that resolves user from access cookie."""
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    data = _decode(access_token)
    if data.get("typ") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session type")

    user_id = uuid.UUID(data["sub"])
    user = _get_user(db, user_id)

    org_id: Optional[uuid.UUID] = None
    if active_org:
        try:
            org_id = uuid.UUID(active_org)
        except ValueError:
            org_id = None

    # If an org cookie is set, ensure user is member.
    if org_id:
        membership = db.scalar(
            select(OrgMembership).where(
                OrgMembership.org_id == org_id, OrgMembership.user_id == user.id, OrgMembership.status == "active"
            )
        )
        if not membership:
            org_id = None

    # Stash basic info for audit helpers.
    request.state.user_id = user.id
    request.state.active_org_id = org_id
    return AuthContext(user=user, active_org_id=org_id)
