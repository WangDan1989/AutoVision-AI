from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.task import TaskQueue
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("")
def list_tasks(project_id: str | None = None, db: Session = Depends(get_db)):
    stmt = select(TaskQueue).order_by(TaskQueue.created_at.desc()).limit(100)
    if project_id:
        stmt = stmt.where(TaskQueue.project_id == project_id)

    items = list(db.scalars(stmt))
    return ApiResponse(
        request_id=project_id or "tasks",
        data={
            "items": [
                {
                    "id": item.id,
                    "project_id": item.project_id,
                    "step_no": item.step_no,
                    "task_type": item.task_type,
                    "status": item.status,
                    "error_message": item.error_message,
                    "created_at": item.created_at,
                }
                for item in items
            ]
        },
    )
