from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.project import Project
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse
from app.schemas.export import GenerateExportRequest
from app.services.export_service import ExportService

router = APIRouter(prefix="/api", tags=["exports"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/projects/{project_id}/exports/generate")
def generate_export(project_id: str, req: GenerateExportRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        export_job = ExportService(db).create_export(project, req)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(request_id=export_job.id, data={"export_job_id": export_job.id, "output_path": export_job.output_path})


@router.get("/projects/{project_id}/exports")
def list_exports(project_id: str, db: Session = Depends(get_db)):
    return ApiResponse(request_id=project_id, data={"items": ExportService(db).list_exports(project_id)})
