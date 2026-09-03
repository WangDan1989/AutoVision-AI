from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.segment import ScriptSegment
from app.db.session import SessionLocal
from app.schemas.common import ApiResponse
from app.schemas.video import GenerateVideoRequest
from app.services.video_service import VideoService

router = APIRouter(prefix="/api", tags=["video"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/segments/{segment_id}/videos/generate")
def generate_video(segment_id: str, req: GenerateVideoRequest, db: Session = Depends(get_db)):
    segment = db.get(ScriptSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="segment not found")
    try:
        clip = VideoService(db).generate_clip(segment, req)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(request_id=clip.id, data={"video_clip_id": clip.id, "video_path": clip.video_path})


@router.get("/projects/{project_id}/videos")
def list_videos(project_id: str, db: Session = Depends(get_db)):
    return ApiResponse(request_id=project_id, data={"items": VideoService(db).list_clips(project_id)})
