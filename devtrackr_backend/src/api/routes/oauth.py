from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.schemas import OAuthCallbackResponse, OAuthStartResponse
from src.core.audit import write_audit_log
from src.core.auth import create_access_token, create_refresh_token
from src.core.db import get_db
from src.core.oauth import build_authorize_url, exchange_code_for_token, fetch_user_profile, generate_oauth_state
from src.core.settings import get_settings
from src.models.models import OAuthAccount, OrgMembership, Organization, User

router = APIRouter(prefix="/oauth", tags=["OAuth"])


def _cookie_params() -> dict:
    settings = get_settings()
    params = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }
    # Allow deployments to share cookies across subdomains when needed.
    # Keep unset by default for localhost / simple preview URLs.
    if settings.cookie_domain:
        params["domain"] = settings.cookie_domain
    return params


def _redirect_uri(provider: str) -> str:
    settings = get_settings()
    return f"{settings.site_url}/oauth/{provider}/callback"


@router.post(
    "/{provider}/start",
    summary="Start OAuth flow",
    response_model=OAuthStartResponse,
)
def start(provider: str, response: Response) -> OAuthStartResponse:
    """Create an OAuth state cookie and return provider authorization URL."""
    provider = provider.lower()
    if provider not in ("github", "gitlab"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider")

    state = generate_oauth_state()
    response.set_cookie("devtrackr_oauth_state", state, **_cookie_params())
    url = build_authorize_url(provider, state=state, redirect_uri=_redirect_uri(provider))
    return OAuthStartResponse(url=url)


@router.get(
    "/{provider}/callback",
    summary="OAuth callback endpoint",
    response_model=OAuthCallbackResponse,
)
async def callback(
    provider: str,
    request: Request,
    response: Response,
    code: str | None = None,
    state: str | None = None,
    db: Session = Depends(get_db),
    oauth_state_cookie: str | None = None,
) -> OAuthCallbackResponse:
    """
    OAuth callback endpoint.

    The frontend can hit this directly or via its own callback page; backend sets session cookies.
    """
    provider = provider.lower()
    if provider not in ("github", "gitlab"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported provider")

    # Read state cookie manually from request cookies (FastAPI Cookie aliasing is awkward for dynamic flows).
    cookie_state = request.cookies.get("devtrackr_oauth_state")
    if not state or not cookie_state or state != cookie_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    if not code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code")

    token = await exchange_code_for_token(provider, code=code, redirect_uri=_redirect_uri(provider))
    access_token = token.get("access_token")
    if not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token exchange failed")

    profile = await fetch_user_profile(provider, access_token=access_token)

    # Normalize profile -> provider_account_id/username/email
    if provider == "github":
        provider_account_id = str(profile.get("id"))
        username = profile.get("login")
        email = profile.get("email")  # may be null if private
        avatar = profile.get("avatar_url")
        display_name = profile.get("name") or username
    else:
        provider_account_id = str(profile.get("id"))
        username = profile.get("username")
        email = profile.get("email")
        avatar = profile.get("avatar_url")
        display_name = profile.get("name") or username

    # Upsert user
    user = None
    if email:
        user = db.scalar(select(User).where(User.email == email))
    if not user:
        user = User(email=email, display_name=display_name, avatar_url=avatar, last_login_at=datetime.now(timezone.utc))
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        user.last_login_at = datetime.now(timezone.utc)
        user.display_name = user.display_name or display_name
        user.avatar_url = user.avatar_url or avatar
        db.add(user)
        db.commit()

    # Upsert OAuth account
    acct = db.scalar(
        select(OAuthAccount).where(OAuthAccount.provider == provider, OAuthAccount.provider_account_id == provider_account_id)
    )
    if not acct:
        acct = OAuthAccount(
            user_id=user.id,
            provider=provider,
            provider_account_id=provider_account_id,
            provider_username=username,
            access_token=access_token,
            refresh_token=token.get("refresh_token"),
            token_type=token.get("token_type"),
            scope=token.get("scope"),
            raw_profile=profile,
        )
        db.add(acct)
    else:
        acct.user_id = user.id
        acct.provider_username = username
        acct.access_token = access_token
        acct.refresh_token = token.get("refresh_token")
        acct.scope = token.get("scope")
        acct.raw_profile = profile
        db.add(acct)
    db.commit()

    # Ensure demo org membership exists for new users (seed org: demo)
    demo_org = db.scalar(select(Organization).where(Organization.slug == "demo"))
    if demo_org:
        membership = db.scalar(
            select(OrgMembership).where(OrgMembership.org_id == demo_org.id, OrgMembership.user_id == user.id)
        )
        if not membership:
            membership = OrgMembership(org_id=demo_org.id, user_id=user.id, status="active")
            db.add(membership)
            db.commit()

    # Write audit entry
    write_audit_log(
        db,
        request=request,
        action="oauth.connect",
        org_id=demo_org.id if demo_org else None,
        entity_type="oauth_account",
        entity_id=uuid.UUID(acct.id) if isinstance(acct.id, str) else acct.id,
        metadata={"provider": provider, "username": username},
    )

    # Set session cookies
    response.set_cookie("devtrackr_access", create_access_token(user.id), **_cookie_params())
    response.set_cookie("devtrackr_refresh", create_refresh_token(user.id), **_cookie_params())
    if demo_org:
        response.set_cookie("devtrackr_active_org", str(demo_org.id), **_cookie_params())

    # Clear oauth state cookie
    response.delete_cookie("devtrackr_oauth_state", path="/")

    # Optionally redirect back to frontend if requested
    # (Frontend can choose to call this and handle redirect itself.)
    return OAuthCallbackResponse(ok=True)
