from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.auth import AuthContext, get_auth_context
from src.core.db import get_db
from src.models.models import MembershipRole, OrgMembership, Permission, RolePermission


def _has_permission(db: Session, org_id: uuid.UUID, user_id: uuid.UUID, permission_key: str) -> bool:
    membership = db.scalar(
        select(OrgMembership).where(
            OrgMembership.org_id == org_id, OrgMembership.user_id == user_id, OrgMembership.status == "active"
        )
    )
    if not membership:
        return False

    # Join membership_roles -> role_permissions -> permissions
    perm = db.scalar(
        select(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(MembershipRole, MembershipRole.role_id == RolePermission.role_id)
        .where(MembershipRole.membership_id == membership.id, Permission.key == permission_key)
        .limit(1)
    )
    return perm is not None


# PUBLIC_INTERFACE
def require_permission(permission_key: str) -> Callable:
    """Return a dependency that enforces a permission for the current active org."""

    def _dep(ctx: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)) -> AuthContext:
        if ctx.user.is_superadmin:
            return ctx
        if not ctx.active_org_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No active organization selected")
        if not _has_permission(db, ctx.active_org_id, ctx.user.id, permission_key):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return ctx

    return _dep
