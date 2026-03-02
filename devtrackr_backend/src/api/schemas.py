from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    message: str = Field(..., description="Health check status message.")


class UserOut(BaseModel):
    id: uuid.UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class OrgOut(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class RepoOut(BaseModel):
    id: uuid.UUID
    org_id: uuid.UUID
    provider: str
    full_name: str
    is_active: bool = True


class PullRequestOut(BaseModel):
    id: uuid.UUID
    repo_id: uuid.UUID
    provider: str
    title: str
    state: str
    url: Optional[str] = None
    created_at: Optional[datetime] = None
    risk_score: Optional[float] = None
    summary: Optional[str] = None
    risk_notes: list[str] = Field(default_factory=list)


class AuditOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[uuid.UUID] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class OAuthStartResponse(BaseModel):
    url: str = Field(..., description="Authorization URL to redirect the user to.")


class OAuthCallbackResponse(BaseModel):
    ok: bool = True


class SessionMeResponse(BaseModel):
    user: UserOut
    active_org_id: Optional[uuid.UUID] = None


class SetActiveOrgRequest(BaseModel):
    org_id: uuid.UUID


class UpdateUserRoleRequest(BaseModel):
    role: Literal["owner", "admin", "member"]


class AnalyticsDailyOrgOut(BaseModel):
    org_id: uuid.UUID
    day: date
    commits_count: int
    prs_opened_count: int
    prs_merged_count: int
    active_developers_count: int
    avg_pr_cycle_hours: Optional[float] = None
    avg_risk_score: Optional[float] = None
