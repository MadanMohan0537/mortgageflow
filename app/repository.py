from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, AuditEvent


def application_scope(actor: str, role: str):
    query = select(Application)
    if role != "reviewer":
        query = query.where(Application.owner_id == actor)
    return query


def find_application(db: Session, app_id: UUID, actor: str, role: str, *, lock: bool = False):
    query = application_scope(actor, role).where(Application.id == app_id)
    return db.scalar(query.with_for_update() if lock else query)


def audit(db: Session, app_id: UUID, actor: str, action: str, correlation: str) -> None:
    db.add(
        AuditEvent(
            application_id=app_id,
            actor_id=actor,
            action=action,
            correlation_id=correlation,
        )
    )
