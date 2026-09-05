from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models.asset import Asset
from app.db.models.project import Project
from app.db.session import SessionLocal
from app.schemas.asset import BindingRequest, SaveConsistencyRequest
from app.schemas.common import ApiResponse
from app.services.asset_service import AssetService

router = APIRouter(prefix="/api", tags=["assets"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/projects/{project_id}/assets/rebuild")
async def rebuild_assets(project_id: str, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="project not found")
    try:
        items = await AssetService(db).rebuild_assets(project)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(request_id=project_id, data={"count": len(items)})


@router.get("/projects/{project_id}/assets")
def list_assets(project_id: str, db: Session = Depends(get_db)):
    return ApiResponse(request_id=project_id, data={"items": AssetService(db).list_assets(project_id)})


@router.post("/assets/{asset_id}/bindings")
def save_binding(asset_id: str, req: BindingRequest, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    binding = AssetService(db).save_binding(asset, req)
    return ApiResponse(
        request_id=binding.id,
        data={
            "id": binding.id,
            "asset_id": binding.asset_id,
            "binding_mode": binding.binding_mode,
            "lora_enabled": bool(binding.lora_enabled),
        },
    )


@router.post("/assets/{asset_id}/consistency")
def save_consistency(asset_id: str, req: SaveConsistencyRequest, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    updated = AssetService(db).save_consistency(asset, req)
    return ApiResponse(
        request_id=updated.id,
        data={
            "id": updated.id,
            "asset_id": updated.id,
            "consistency_updated": True,
        },
    )
