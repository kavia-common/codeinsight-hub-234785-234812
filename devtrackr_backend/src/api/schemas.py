from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    message: str = Field(..., description="Health check status message.")


class UserOut(BaseModel):
    id: str = Field(..., description="User id as string (UUID).")
    email: Optional[str] = None
    name: Optional[str] = Field(default=None, description="Display name (frontend expects `name`).")
    display_name: Optional[str] = Field(default=None, description="Back-compat field (same as name).")
    avatar_url: Optional[str] = None
    role: Optional[str] = Field(default=None, description="Optional org role label for UI surfaces.")
    status: Optional[str] = Field(default=None, description="Membership status (active/invited), if applicable.")


class OrgOut(BaseModel):
    id: str = Field(..., description="Organization id as string (UUID).")
    name: str = Field(..., description="Organization display name (frontend expects `name`).")


class RepoOut(BaseModel):
    id: str = Field(..., description="Repository id as string (UUID).")
    name: str = Field(..., description="Short repo name derived from full name.")
    fullName: str = Field(..., description="Provider full name (e.g. org/repo).")
    provider: str
    isSynced: bool = Field(..., description="Whether repo is synced/enabled (maps to is_active).")


class PullRequestOut(BaseModel):
    id: str = Field(..., description="PR id as string (UUID).")
    number: Optional[int] = Field(default=None, description="Provider PR number, when available.")
    title: str
    author: Optional[str] = Field(default=None, description="Author username, when known.")
    createdAt: Optional[datetime] = Field(default=None, description="Creation timestamp (frontend expects `createdAt`).")
    provider: str
    repoFullName: Optional[str] = Field(default=None, description="Repo full name for UI lists.")
    summary: Optional[str] = None
    riskScore: Optional[float] = None
    riskNotes: list[str] = Field(default_factory=list)


class AuditOut(BaseModel):
    id: str = Field(..., description="Audit event id as string (UUID).")
    ts: datetime = Field(..., description="Event timestamp (frontend expects `ts`).")
    actor: Optional[str] = Field(default=None, description="Actor identifier (best-effort).")
    action: str
    target: Optional[str] = Field(default=None, description="Entity target display (best-effort).")
    meta: Optional[str] = Field(default=None, description="Short metadata string for display (best-effort).")


class BillingStateOut(BaseModel):
    plan: str = Field(..., description="Plan key (e.g. free/pro).")
    seatsUsed: int = Field(..., description="Current seats used.")
    seatsLimit: int = Field(..., description="Seat limit for plan.")
    renewalDate: datetime = Field(..., description="Renewal date/time.")


class OAuthStartResponse(BaseModel):
    url: str = Field(..., description="Authorization URL to redirect the user to.")


class OAuthCallbackResponse(BaseModel):
    ok: bool = True


class SessionMeResponse(BaseModel):
    user: UserOut
    active_org_id: Optional[str] = None


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
