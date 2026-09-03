from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.segment import ScriptSegment
from app.db.session import SessionLocal
from app.schemas.audio import GenerateAudioRequest
from app.schemas.common import ApiResponse
from app.services.tts_service import TTSService

router = APIRouter(prefix="/api", tags=["audio"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/segments/{segment_id}/audio/generate")
async def generate_audio(segment_id: str, req: GenerateAudioRequest, db: Session = Depends(get_db)):
    segment = db.get(ScriptSegment, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="segment not found")
    try:
        track = await TTSService(db).generate_segment_audio(segment, req)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return ApiResponse(request_id=track.id, data={"audio_track_id": track.id, "audio_path": track.audio_path})


@router.get("/projects/{project_id}/audio")
def list_audio(project_id: str, db: Session = Depends(get_db)):
    return ApiResponse(request_id=project_id, data={"items": TTSService(db).list_tracks(project_id)})
