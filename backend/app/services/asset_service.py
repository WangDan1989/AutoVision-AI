import json
from collections import OrderedDict

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.enums import AssetType, JobStatus
from app.db.models.asset import Asset, AssetBinding
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.schemas.asset import BindingRequest
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class AssetService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _ordered_unique(self, items: list[str]) -> list[str]:
        bag: OrderedDict[str, bool] = OrderedDict()
        for item in items:
            name = item.strip()
            if name:
                bag[name] = True
        return list(bag.keys())

    def rebuild_assets(self, project: Project) -> list[Asset]:
        segments = list(
            self.db.scalars(
                select(ScriptSegment).where(ScriptSegment.project_id == project.id).order_by(ScriptSegment.seq_no.asc())
            )
        )
        if not segments:
            raise ValueError("当前项目还没有分镜数据")

        characters: list[str] = []
        scenes: list[str] = []
        for seg in segments:
            characters.extend(json.loads(seg.character_ids_json or "[]"))
            if seg.scene_name.strip():
                scenes.append(seg.scene_name.strip())

        self.db.execute(delete(AssetBinding).where(AssetBinding.project_id == project.id))
        self.db.execute(delete(Asset).where(Asset.project_id == project.id))

        now = utc_now_iso()
        created: list[Asset] = []

        for name in self._ordered_unique(characters):
            created.append(
                Asset(
                    id=new_id(),
                    project_id=project.id,
                    asset_type=AssetType.CHARACTER.value,
                    name=name,
                    canonical_name=name,
                    description="",
                    cover_image_path="",
                    status=JobStatus.COMPLETED.value,
                    created_at=now,
                    updated_at=now,
                )
            )

        for name in self._ordered_unique(scenes):
            created.append(
                Asset(
                    id=new_id(),
                    project_id=project.id,
                    asset_type=AssetType.SCENE.value,
                    name=name,
                    canonical_name=name,
                    description="",
                    cover_image_path="",
                    status=JobStatus.COMPLETED.value,
                    created_at=now,
                    updated_at=now,
                )
            )

        self.db.add_all(created)
        project.current_step_unlock = max(project.current_step_unlock, 2)
        project.updated_at = now
        self.db.commit()
        return created

    def list_assets(self, project_id: str) -> list[dict]:
        assets = list(self.db.scalars(select(Asset).where(Asset.project_id == project_id).order_by(Asset.asset_type.asc(), Asset.name.asc())))
        result: list[dict] = []
        for asset in assets:
            binding = self.db.scalar(
                select(AssetBinding).where(AssetBinding.asset_id == asset.id, AssetBinding.variant_id.is_(None))
            )
            result.append(
                {
                    "id": asset.id,
                    "project_id": asset.project_id,
                    "asset_type": asset.asset_type,
                    "name": asset.name,
                    "canonical_name": asset.canonical_name,
                    "status": asset.status,
                    "binding": None
                    if not binding
                    else {
                        "id": binding.id,
                        "binding_mode": binding.binding_mode,
                        "lora_enabled": bool(binding.lora_enabled),
                        "lora_file_path": binding.lora_file_path,
                        "lora_weight": binding.lora_weight,
                        "trigger_word": binding.trigger_word,
                        "ip_adapter_enabled": bool(binding.ip_adapter_enabled),
                        "ip_adapter_weight": binding.ip_adapter_weight,
                        "reference_image_paths": json.loads(binding.reference_image_paths_json or "[]"),
                        "decouple_clothes": bool(binding.decouple_clothes),
                    },
                }
            )
        return result

    def save_binding(self, asset: Asset, req: BindingRequest) -> AssetBinding:
        binding = self.db.scalar(select(AssetBinding).where(AssetBinding.asset_id == asset.id, AssetBinding.variant_id.is_(None)))
        now = utc_now_iso()

        if not binding:
            binding = AssetBinding(
                id=new_id(),
                project_id=asset.project_id,
                asset_id=asset.id,
                variant_id=None,
                created_at=now,
                updated_at=now,
                status=JobStatus.COMPLETED.value,
                binding_mode=req.binding_mode,
                lora_enabled=1 if req.lora_enabled else 0,
                lora_file_path=req.lora_file_path,
                lora_weight=req.lora_weight,
                trigger_word=req.trigger_word,
                ip_adapter_enabled=1 if req.ip_adapter_enabled else 0,
                ip_adapter_weight=req.ip_adapter_weight,
                reference_image_paths_json=json.dumps(req.reference_image_paths, ensure_ascii=False),
                decouple_clothes=1 if req.decouple_clothes else 0,
            )
            self.db.add(binding)
        else:
            binding.updated_at = now
            binding.binding_mode = req.binding_mode
            binding.lora_enabled = 1 if req.lora_enabled else 0
            binding.lora_file_path = req.lora_file_path
            binding.lora_weight = req.lora_weight
            binding.trigger_word = req.trigger_word
            binding.ip_adapter_enabled = 1 if req.ip_adapter_enabled else 0
            binding.ip_adapter_weight = req.ip_adapter_weight
            binding.reference_image_paths_json = json.dumps(req.reference_image_paths, ensure_ascii=False)
            binding.decouple_clothes = 1 if req.decouple_clothes else 0

        asset_project = self.db.get(Project, asset.project_id)
        if asset_project:
            total_assets = self.db.scalar(select(func.count()).select_from(Asset).where(Asset.project_id == asset.project_id)) or 0
            total_bindings = self.db.scalar(select(func.count()).select_from(AssetBinding).where(AssetBinding.project_id == asset.project_id)) or 0
            if total_assets and total_bindings >= total_assets:
                asset_project.current_step_unlock = max(asset_project.current_step_unlock, 3)
                asset_project.updated_at = now

        self.db.commit()
        self.db.refresh(binding)
        return binding
