from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.frame import StoryboardFrame
from app.db.models.segment import ScriptSegment
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse
from app.schemas.storyboard import GenerateFrameRequest, LockFrameRequest
from app.services.storyboard_service import StoryboardService

router = APIRouter(prefix="/api", tags=["storyboard"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/segments/{segment_id}/frames/generate")
async def generate_frame(segment_id: str, req: GenerateFrameRequest, db: Session = Depends(get_db)):
    segment = db.get(ScriptSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="segment not found")
    try:
        frame = await StoryboardService(db).generate_frame(segment, req)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(request_id=frame.id, data={"frame_id": frame.id, "image_path": frame.image_path})


@router.post("/frames/{frame_id}/lock")
def lock_frame(frame_id: str, req: LockFrameRequest, db: Session = Depends(get_db)):
    frame = db.get(StoryboardFrame, frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="frame not found")
    frame = StoryboardService(db).lock_frame(frame, req.is_locked)
    return ApiResponse(request_id=frame.id, data={"id": frame.id, "is_locked": bool(frame.is_locked)})


@router.get("/projects/{project_id}/frames")
def list_frames(project_id: str, db: Session = Depends(get_db)):
    return ApiResponse(request_id=project_id, data={"items": StoryboardService(db).list_frames(project_id)})
