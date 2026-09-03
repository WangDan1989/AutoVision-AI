from sqlalchemy.orm import Session

from app.core.enums import JobStatus
from app.db.models.task import TaskQueue
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class TaskLogService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, project_id: str, step_no: int, task_type: str, entity_type: str, entity_id: str, payload_json: str = "{}") -> TaskQueue:
        now = utc_now_iso()
        task = TaskQueue(
            id=new_id(),
            project_id=project_id,
            step_no=step_no,
            task_type=task_type,
            entity_type=entity_type,
            entity_id=entity_id,
            status=JobStatus.RUNNING.value,
            payload_json=payload_json,
            result_json="{}",
            created_at=now,
            updated_at=now,
            started_at=now,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def complete(self, task: TaskQueue, result_json: str = "{}") -> None:
        task.status = JobStatus.COMPLETED.value
        task.result_json = result_json
        task.finished_at = utc_now_iso()
        task.updated_at = task.finished_at
        self.db.commit()

    def fail(self, task: TaskQueue, error_message: str, error_code: str = "TASK_ERROR") -> None:
        task.status = JobStatus.FAILED.value
        task.error_code = error_code
        task.error_message = error_message
        task.finished_at = utc_now_iso()
        task.updated_at = task.finished_at
        self.db.commit()
