from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from datetime import datetime, timedelta, timezone

from src.api.schemas import (
    AnalyticsDailyOrgOut,
    AuditOut,
    BillingStateOut,
    OrgOut,
    PullRequestOut,
    RepoOut,
    UpdateUserRoleRequest,
    UserOut,
)
from src.core.audit import write_audit_log
from src.core.auth import AuthContext, get_auth_context
from src.core.db import get_db
from src.core.rbac import require_permission
from src.models.models import (
    AnalyticsDailyOrg,
    AuditLog,
    OrgMembership,
    Organization,
    PullRequest,
    Repository,
    User,
)

router = APIRouter(prefix="/orgs", tags=["Orgs"])


@router.get(
    "",
    summary="List organizations accessible to current user",
    response_model=list[OrgOut],
)
def list_orgs(ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)) -> list[OrgOut]:
    """List orgs for which the user has an active membership."""
    rows = (
        db.query(Organization)
        .join(OrgMembership, OrgMembership.org_id == Organization.id)
        .filter(OrgMembership.user_id == ctx.user.id, OrgMembership.status == "active")
        .order_by(Organization.name.asc())
        .all()
    )
    return [OrgOut(id=str(o.id), name=o.name) for o in rows]


@router.get(
    "/{org_id}/repos",
    summary="List repositories for an organization",
    response_model=list[RepoOut],
)
def list_repos(
    org_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("repo:read")),
    db: Session = Depends(get_db),
) -> list[RepoOut]:
    """List repos for org."""
    repos = db.query(Repository).filter(Repository.org_id == org_id, Repository.is_active.is_(True)).all()

    def _short_name(full_name: str) -> str:
        # "org/repo" -> "repo"
        return (full_name.split("/", 1)[1] if "/" in full_name else full_name) or full_name

    return [
        RepoOut(
            id=str(r.id),
            name=_short_name(r.full_name),
            fullName=r.full_name,
            provider=r.provider,
            isSynced=bool(r.is_active),
        )
        for r in repos
    ]


@router.get(
    "/{org_id}/prs",
    summary="List PRs/MRs for an organization",
    response_model=list[PullRequestOut],
)
def list_prs(
    org_id: uuid.UUID,
    repoId: Optional[uuid.UUID] = Query(default=None, description="Filter by repo id"),
    provider: Optional[str] = Query(default=None, description="Filter by provider (github|gitlab)"),
    _: AuthContext = Depends(require_permission("repo:read")),
    db: Session = Depends(get_db),
) -> list[PullRequestOut]:
    """List pull/merge requests (unified model)."""
    q = db.query(PullRequest).filter(PullRequest.org_id == org_id)
    if repoId:
        q = q.filter(PullRequest.repo_id == repoId)
    if provider:
        q = q.filter(PullRequest.provider == provider)
    q = q.order_by(PullRequest.created_at.desc().nullslast()).limit(200)
    prs = q.all()

    # Best-effort map: include repo full name for UI without requiring extra joins.
    repo_ids = {p.repo_id for p in prs if p.repo_id}
    repo_map: dict[uuid.UUID, str] = {}
    if repo_ids:
        repos = db.query(Repository).filter(Repository.id.in_(list(repo_ids))).all()
        repo_map = {r.id: r.full_name for r in repos}

    return [
        PullRequestOut(
            id=str(p.id),
            number=p.number or p.iid,
            title=p.title,
            author=p.author_username,
            createdAt=p.created_at,
            provider=p.provider,
            repoFullName=repo_map.get(p.repo_id),
            summary=None,
            riskScore=None,
            riskNotes=[],
        )
        for p in prs
    ]


@router.get(
    "/{org_id}/prs/{pr_id}",
    summary="Get PR/MR details",
    response_model=PullRequestOut,
)
def get_pr(
    org_id: uuid.UUID,
    pr_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("repo:read")),
    db: Session = Depends(get_db),
) -> PullRequestOut:
    """Get PR/MR record."""
    pr = db.get(PullRequest, pr_id)
    if not pr or pr.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

    repo = db.get(Repository, pr.repo_id) if pr.repo_id else None

    return PullRequestOut(
        id=str(pr.id),
        number=pr.number or pr.iid,
        title=pr.title,
        author=pr.author_username,
        createdAt=pr.created_at,
        provider=pr.provider,
        repoFullName=repo.full_name if repo else None,
        summary=None,
        riskScore=None,
        riskNotes=[],
    )


@router.get(
    "/{org_id}/audit",
    summary="List audit logs",
    response_model=list[AuditOut],
)
def list_audit(
    org_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
) -> list[AuditOut]:
    """Return recent audit events for an org."""
    events = (
        db.query(AuditLog)
        .filter(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(200)
        .all()
    )
    return [
        AuditOut(
            id=str(e.id),
            ts=e.created_at,
            actor=str(e.actor_user_id) if e.actor_user_id else None,
            action=e.action,
            target=e.entity_type,
            meta=(e.metadata.get("provider") if isinstance(e.metadata, dict) else None),
        )
        for e in events
    ]


@router.get(
    "/{org_id}/analytics/daily",
    summary="Get org daily analytics rows",
    response_model=list[AnalyticsDailyOrgOut],
)
def org_analytics_daily(
    org_id: uuid.UUID,
    start: Optional[date] = Query(default=None),
    end: Optional[date] = Query(default=None),
    _: AuthContext = Depends(require_permission("org:read")),
    db: Session = Depends(get_db),
) -> list[AnalyticsDailyOrgOut]:
    """Fetch precomputed daily analytics (table-based)."""
    q = db.query(AnalyticsDailyOrg).filter(AnalyticsDailyOrg.org_id == org_id)
    if start:
        q = q.filter(AnalyticsDailyOrg.day >= start)
    if end:
        q = q.filter(AnalyticsDailyOrg.day <= end)
    q = q.order_by(AnalyticsDailyOrg.day.asc())
    rows = q.all()
    return [
        AnalyticsDailyOrgOut(
            org_id=r.org_id,
            day=r.day,
            commits_count=r.commits_count,
            prs_opened_count=r.prs_opened_count,
            prs_merged_count=r.prs_merged_count,
            active_developers_count=r.active_developers_count,
            avg_pr_cycle_hours=float(r.avg_pr_cycle_hours) if r.avg_pr_cycle_hours is not None else None,
            avg_risk_score=float(r.avg_risk_score) if r.avg_risk_score is not None else None,
        )
        for r in rows
    ]


@router.get(
    "/{org_id}/users",
    summary="List users in organization (admin)",
    response_model=list[UserOut],
)
def list_users(
    org_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("org:admin")),
    db: Session = Depends(get_db),
) -> list[UserOut]:
    """List users for org admin page."""
    rows = (
        db.query(User, OrgMembership)
        .join(OrgMembership, OrgMembership.user_id == User.id)
        .filter(OrgMembership.org_id == org_id)
        .order_by(User.created_at.desc())
        .all()
    )

    # For the happy-path demo flow, we don't fully materialize roles; the UI mainly needs shape.
    # We map status from membership; role is a best-effort placeholder.
    out: list[UserOut] = []
    for user, membership in rows:
        out.append(
            UserOut(
                id=str(user.id),
                email=user.email,
                name=user.display_name,
                display_name=user.display_name,
                avatar_url=user.avatar_url,
                role="member",
                status=membership.status,
            )
        )
    return out


@router.patch(
    "/{org_id}/users/{user_id}/role",
    summary="Update user role (simplified)",
)
def update_user_role(
    org_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: UpdateUserRoleRequest,
    request: Request,
    ctx: AuthContext = Depends(require_permission("org:admin")),
    db: Session = Depends(get_db),
) -> dict:
    """
    Simplified role update endpoint.

    Note: The database supports full RBAC tables; this endpoint only writes an audit record for now.
    A full membership_roles update can be added once UI exposes roles list.
    """
    membership = db.scalar(
        select(OrgMembership).where(and_(OrgMembership.org_id == org_id, OrgMembership.user_id == user_id))
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")

    write_audit_log(
        db,
        request=request,
        action="membership.role.update",
        org_id=org_id,
        entity_type="org_membership",
        entity_id=membership.id,
        metadata={"new_role": payload.role, "by": str(ctx.user.id)},
    )
    return {"ok": True}


@router.get(
    "/{org_id}/billing",
    summary="Get billing state (demo)",
    response_model=BillingStateOut,
)
def get_billing(
    org_id: uuid.UUID,
    _: AuthContext = Depends(require_permission("org:read")),
) -> BillingStateOut:
    """Return a deterministic billing payload for the UI happy-path demo flow."""
    now = datetime.now(timezone.utc)
    return BillingStateOut(
        plan="pro",
        seatsUsed=7,
        seatsLimit=10,
        renewalDate=now + timedelta(days=12),
    )
