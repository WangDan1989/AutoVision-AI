from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.project import Project
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse
from app.schemas.project import CreateProjectRequest, UpdateProjectPreferencesRequest
from app.services.project_service import ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("")
def create_project(req: CreateProjectRequest, db: Session = Depends(get_db)):
    project = ProjectService(db).create_project(req)
    return ApiResponse(
        request_id=project.id,
        data={
            "id": project.id,
            "name": project.name,
            "status": project.status,
            "current_step_unlock": project.current_step_unlock,
        },
    )


@router.get("")
def list_projects(db: Session = Depends(get_db)):
    items = list(db.scalars(select(Project).order_by(Project.created_at.desc())))
    return ApiResponse(
        request_id="projects",
        data={
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "status": item.status,
                    "current_step_unlock": item.current_step_unlock,
                    "updated_at": item.updated_at,
                }
                for item in items
            ]
        },
    )


@router.get("/{project_id}")
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    service = ProjectService(db)

    return ApiResponse(
        request_id=project_id,
        data={
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "status": project.status,
            "current_step_unlock": project.current_step_unlock,
            "aspect_ratio": project.aspect_ratio,
            "target_width": project.target_width,
            "target_height": project.target_height,
            "fps": project.fps,
            "preferences": service.get_preferences(project),
            "updated_at": project.updated_at,
        },
    )


@router.patch("/{project_id}/preferences")
def update_project_preferences(
    project_id: str,
    req: UpdateProjectPreferencesRequest,
    db: Session = Depends(get_db),
):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")

    service = ProjectService(db)
    updated = service.update_preferences(
        project,
        req.model_dump(exclude_none=True),
    )
    return ApiResponse(
        request_id=project_id,
        data={
            "id": updated.id,
            "preferences": service.get_preferences(updated),
            "updated_at": updated.updated_at,
        },
    )
