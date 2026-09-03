from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.core.config import settings
from app.schemas.common import ApiResponse
from app.utils.ids import new_id

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("/mask")
async def upload_mask(file: UploadFile = File(...)):
    suffix = Path(file.filename or "mask.png").suffix or ".png"
    filename = f"mask_{new_id()}{suffix}"
    target_path = settings.media_root_path / settings.TEMP_DIR / filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(await file.read())

    return ApiResponse(
        request_id=filename,
        data={
            "file_name": filename,
            "abs_path": str(target_path),
            "relative_path": f"{settings.TEMP_DIR}/{filename}",
        },
    )
