from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.core.audit import write_audit_log
from src.core.db import get_db
from src.core.rbac import require_permission
from src.models.models import Repository
from src.services.sync import enqueue_repo_sync

router = APIRouter(prefix="/orgs/{org_id}/repos", tags=["Repos"])


@router.post(
    "/{repo_id}/sync",
    summary="Trigger repository sync (stubbed)",
)
def sync_repo(
    org_id: uuid.UUID,
    repo_id: uuid.UUID,
    request: Request,
    _: object = Depends(require_permission("sync:run")),
    db: Session = Depends(get_db),
) -> dict:
    """Trigger sync job placeholder."""
    repo = db.get(Repository, repo_id)
    if not repo or repo.org_id != org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repo not found")

    payload = enqueue_repo_sync(db, org_id=org_id, repo_id=repo_id)
    write_audit_log(
        db,
        request=request,
        action="repo.sync.enqueue",
        org_id=org_id,
        entity_type="repository",
        entity_id=repo_id,
        metadata=payload,
    )
    return payload
