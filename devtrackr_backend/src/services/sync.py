from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models.models import Repository


# PUBLIC_INTERFACE
def enqueue_repo_sync(db: Session, *, org_id: uuid.UUID, repo_id: uuid.UUID, sync_type: str = "full") -> dict:
    """
    Enqueue a repository sync.

    This is a stub (no worker queue). It validates the repository exists and returns a job-like payload.
    """
    repo = db.get(Repository, repo_id)
    if not repo or repo.org_id != org_id:
        raise ValueError("Repository not found")

    # Future: insert repo_sync_runs + background worker enqueue.
    return {
        "job_id": str(uuid.uuid4()),
        "repo_id": str(repo_id),
        "org_id": str(org_id),
        "sync_type": sync_type,
        "status": "queued",
        "queued_at": datetime.now(timezone.utc).isoformat(),
    }
