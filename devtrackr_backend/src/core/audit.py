from __future__ import annotations

import uuid
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from src.models.models import AuditLog


# PUBLIC_INTERFACE
def write_audit_log(
    db: Session,
    *,
    request: Request,
    action: str,
    org_id: Optional[uuid.UUID],
    entity_type: Optional[str] = None,
    entity_id: Optional[uuid.UUID] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persist an audit log event."""
    actor_user_id = getattr(request.state, "user_id", None)
    actor_ip = request.client.host if request.client else None
    actor_ua = request.headers.get("user-agent")

    row = AuditLog(
        org_id=org_id,
        actor_user_id=actor_user_id,
        actor_ip=actor_ip,
        actor_user_agent=actor_ua,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata or {},
    )
    db.add(row)
    db.commit()
