from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from src.core.auth import AuthContext, create_access_token, create_refresh_token, get_auth_context
from src.core.db import get_db
from src.core.settings import get_settings
from src.models.models import OrgMembership
from src.api.schemas import SessionMeResponse, SetActiveOrgRequest, UserOut

router = APIRouter(prefix="/auth", tags=["Auth"])


def _cookie_params() -> dict:
    settings = get_settings()
    return {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.cookie_samesite,
        "path": "/",
    }


@router.get(
    "/me",
    summary="Get current session user",
    response_model=SessionMeResponse,
)
def me(ctx: AuthContext = Depends(get_auth_context)) -> SessionMeResponse:
    """Return current session user and active organization."""
    return SessionMeResponse(
        user=UserOut(id=ctx.user.id, email=ctx.user.email, display_name=ctx.user.display_name, avatar_url=ctx.user.avatar_url),
        active_org_id=ctx.active_org_id,
    )


@router.post(
    "/logout",
    summary="Logout (clear cookies)",
)
def logout(response: Response) -> dict:
    """Clear session cookies."""
    response.delete_cookie("devtrackr_access", path="/")
    response.delete_cookie("devtrackr_refresh", path="/")
    response.delete_cookie("devtrackr_active_org", path="/")
    return {"ok": True}


@router.post(
    "/active-org",
    summary="Set active organization for RBAC checks",
)
def set_active_org(
    payload: SetActiveOrgRequest,
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> dict:
    """Set active org cookie after validating membership."""
    membership = (
        db.query(OrgMembership)
        .filter(OrgMembership.org_id == payload.org_id, OrgMembership.user_id == ctx.user.id, OrgMembership.status == "active")
        .first()
    )
    if not membership:
        return {"ok": False, "error": "Not a member"}

    response.set_cookie("devtrackr_active_org", str(payload.org_id), **_cookie_params())
    # Refresh access token so clients don't get stuck with older sub fields later (future proof).
    response.set_cookie("devtrackr_access", create_access_token(ctx.user.id), **_cookie_params())
    response.set_cookie("devtrackr_refresh", create_refresh_token(ctx.user.id), **_cookie_params())
    return {"ok": True}
