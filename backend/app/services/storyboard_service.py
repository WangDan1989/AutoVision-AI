import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import JobStatus, TaskType
from app.db.models.asset import Asset, AssetBinding
from app.db.models.frame import StoryboardFrame
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.schemas.storyboard import GenerateFrameRequest
from app.services.comfyui_service import ComfyUIService
from app.services.task_log_service import TaskLogService
from app.utils.files import to_relative_media_path
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class StoryboardService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.comfy = ComfyUIService()
        self.task_log = TaskLogService(db)

    def _get_segment_lora(self, segment: ScriptSegment) -> tuple[str, float, str]:
        character_names = json.loads(segment.character_ids_json or "[]")
        if not character_names:
            return "", 0.75, ""

        asset = self.db.scalar(
            select(Asset).where(
                Asset.project_id == segment.project_id,
                Asset.asset_type == "CHARACTER",
                Asset.canonical_name == character_names[0],
            )
        )
        if not asset:
            return "", 0.75, ""

        binding = self.db.scalar(select(AssetBinding).where(AssetBinding.asset_id == asset.id, AssetBinding.variant_id.is_(None)))
        if not binding or not binding.lora_enabled or not binding.lora_file_path:
            return "", 0.75, ""

        return binding.lora_file_path, binding.lora_weight, binding.trigger_word

    async def generate_frame(self, segment: ScriptSegment, req: GenerateFrameRequest) -> StoryboardFrame:
        payload_json = json.dumps(req.model_dump(), ensure_ascii=False)
        task = self.task_log.create(
            project_id=segment.project_id,
            step_no=3,
            task_type=TaskType.KEYFRAME_RENDER.value,
            entity_type="segment",
            entity_id=segment.id,
            payload_json=payload_json,
        )
        try:
            now = utc_now_iso()
            lora_name, lora_weight, trigger_word = self._get_segment_lora(segment)
            positive_prompt = (req.prompt_override or "").strip() or segment.visual_desc
            if trigger_word:
                positive_prompt = f"{trigger_word}, {positive_prompt}"
            render = await self.comfy.generate_image(
                positive_prompt=positive_prompt,
                width=req.width,
                height=req.height,
                filename_prefix=f"{segment.project_id}_{segment.id}_{now.replace(':', '').replace('-', '')}",
                lora_name=lora_name,
                lora_weight=lora_weight,
            )
            latest_ver = (
                self.db.query(StoryboardFrame)
                .filter(StoryboardFrame.segment_id == segment.id, StoryboardFrame.frame_type == "KEYFRAME_START")
                .count()
                + 1
            )
            frame = StoryboardFrame(
                id=new_id(),
                project_id=segment.project_id,
                segment_id=segment.id,
                frame_type="KEYFRAME_START",
                version_no=latest_ver,
                image_path=render["image_path"],
                thumb_path="",
                prompt_text=positive_prompt,
                negative_prompt_text=req.negative_prompt_override,
                width=render["width"],
                height=render["height"],
                is_locked=0,
                source_binding_snapshot_json=json.dumps({"lora_name": lora_name, "lora_weight": lora_weight}, ensure_ascii=False),
                status=JobStatus.COMPLETED.value,
                created_at=now,
                updated_at=now,
            )
            self.db.add(frame)
            project = self.db.get(Project, segment.project_id)
            if project:
                project.updated_at = now
            self.db.commit()
            self.db.refresh(frame)
            self.task_log.complete(task, json.dumps({"frame_id": frame.id, "image_path": frame.image_path}, ensure_ascii=False))
            return frame
        except Exception as exc:
            self.task_log.fail(task, str(exc), "KEYFRAME_RENDER_FAILED")
            raise

    def lock_frame(self, frame: StoryboardFrame, is_locked: bool) -> StoryboardFrame:
        now = utc_now_iso()
        if is_locked:
            frames = list(
                self.db.scalars(
                    select(StoryboardFrame).where(
                        StoryboardFrame.segment_id == frame.segment_id,
                        StoryboardFrame.frame_type == frame.frame_type,
                    )
                )
            )
            for item in frames:
                item.is_locked = 1 if item.id == frame.id else 0
                item.updated_at = now
        else:
            frame.is_locked = 0
            frame.updated_at = now

        project = self.db.get(Project, frame.project_id)
        if project:
            total_segments = self.db.query(ScriptSegment).filter(ScriptSegment.project_id == project.id).count()
            locked_segments = len(
                {
                    item.segment_id
                    for item in self.db.query(StoryboardFrame)
                    .filter(
                        StoryboardFrame.project_id == project.id,
                        StoryboardFrame.frame_type == "KEYFRAME_START",
                        StoryboardFrame.is_locked == 1,
                    )
                    .all()
                }
            )
            if total_segments and locked_segments >= total_segments:
                project.current_step_unlock = max(project.current_step_unlock, 4)
            project.updated_at = now

        self.db.commit()
        self.db.refresh(frame)
        return frame

    def list_frames(self, project_id: str) -> list[dict]:
        frames = list(
            self.db.scalars(
                select(StoryboardFrame).where(StoryboardFrame.project_id == project_id).order_by(StoryboardFrame.created_at.desc())
            )
        )
        return [
            {
                "id": frame.id,
                "segment_id": frame.segment_id,
                "frame_type": frame.frame_type,
                "version_no": frame.version_no,
                "image_path": frame.image_path,
                "image_url": f"/media/{to_relative_media_path(frame.image_path)}?t={frame.updated_at}" if frame.image_path else "",
                "width": frame.width,
                "height": frame.height,
                "is_locked": bool(frame.is_locked),
                "status": frame.status,
                "updated_at": frame.updated_at,
            }
            for frame in frames
        ]
