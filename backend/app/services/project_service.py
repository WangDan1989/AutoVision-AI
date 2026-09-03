from sqlalchemy.orm import Session

from app.core.enums import ProjectStatus
from app.db.models.project import Project
from app.schemas.project import CreateProjectRequest
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, req: CreateProjectRequest) -> Project:
        now = utc_now_iso()
        project = Project(
            id=new_id(),
            name=req.name,
            description=req.description,
            status=ProjectStatus.DRAFT.value,
            current_step_unlock=1,
            aspect_ratio=req.aspect_ratio,
            target_width=req.target_width,
            target_height=req.target_height,
            fps=req.fps,
            raw_script_text="",
            created_at=now,
            updated_at=now,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project
