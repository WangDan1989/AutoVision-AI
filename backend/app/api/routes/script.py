from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.project import Project
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse
from app.schemas.script import ParseScriptRequest
from app.services.script_service import ScriptService

router = APIRouter(prefix="/api/projects", tags=["script"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/{project_id}/script/parse")
async def parse_script(project_id: str, req: ParseScriptRequest, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        result = await ScriptService(db).parse_and_save(project, req.raw_script_text)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(request_id=project_id, data=result)


@router.get("/{project_id}/segments")
def list_segments(project_id: str, db: Session = Depends(get_db)):
    return ApiResponse(
        request_id=project_id,
        data={"items": ScriptService(db).list_segments(project_id)},
    )
