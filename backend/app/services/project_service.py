import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import ProjectStatus
from app.core.config import settings
from app.db.models.asset import Asset, AssetBinding, AssetVariant
from app.db.models.audio import AudioTrack
from app.db.models.export import ExportJob
from app.db.models.file_registry import FileRegistry
from app.db.models.frame import StoryboardFrame
from app.db.models.project import Project
from app.db.models.segment import ScriptSegment
from app.db.models.task import TaskQueue
from app.db.models.video import VideoClip
from app.schemas.project import CreateProjectRequest, ProjectPreferences
from app.utils.ids import new_id
from app.utils.time import utc_now_iso


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_project(self, req: CreateProjectRequest) -> Project:
        now = utc_now_iso()
        project = Project(
            id=new_id(),
            name=req.name,
            description=req.description,
            status=ProjectStatus.DRAFT.value,
            current_step_unlock=1,
            aspect_ratio=req.aspect_ratio,
            target_width=req.target_width,
            target_height=req.target_height,
            fps=req.fps,
            raw_script_text="",
            preferences_json=json.dumps(self.build_default_preferences(req.target_width, req.target_height, req.fps), ensure_ascii=False),
            created_at=now,
            updated_at=now,
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    @staticmethod
    def build_default_preferences(target_width: int, target_height: int, fps: int) -> dict:
        return ProjectPreferences(
            storyboard={
                "prompt_override": "",
                "negative_prompt_override": "",
                "width": target_width,
                "height": target_height,
            },
            media={
                "video_duration_sec": 3,
                "video_fps": fps,
                "video_width": target_width,
                "video_height": target_height,
                "audio_track_type": "NARRATION",
                "audio_voice_profile": "",
            },
            export={
                "subtitle_enabled": True,
                "transition_enabled": True,
            },
        ).model_dump()

    def get_preferences(self, project: Project) -> dict:
        raw = {}
        if project.preferences_json:
            try:
                raw = json.loads(project.preferences_json)
            except json.JSONDecodeError:
                raw = {}
        merged = self.build_default_preferences(project.target_width, project.target_height, project.fps)
        for key in ("storyboard", "media", "export"):
            merged[key].update(raw.get(key, {}))
        return ProjectPreferences.model_validate(merged).model_dump()

    def update_preferences(self, project: Project, preferences_patch: dict) -> Project:
        merged = self.get_preferences(project)
        for key in ("storyboard", "media", "export"):
            value = preferences_patch.get(key)
            if value is not None:
                merged[key].update(value)
        project.preferences_json = json.dumps(
            ProjectPreferences.model_validate(merged).model_dump(),
            ensure_ascii=False,
        )
        project.updated_at = utc_now_iso()
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def _collect_project_file_paths(self, project_id: str) -> set[Path]:
        safe_root = settings.media_root_path.resolve()
        file_paths: set[Path] = set()

        def add_path(raw_path: str) -> None:
            if not raw_path:
                return
            try:
                path = Path(raw_path).expanduser()
                if not path.is_absolute():
                    path = (settings.media_root_path / path).resolve()
                else:
                    path = path.resolve()
            except Exception:
                return
            if safe_root == path or safe_root in path.parents:
                file_paths.add(path)

        for item in self.db.scalars(select(StoryboardFrame).where(StoryboardFrame.project_id == project_id)):
            add_path(item.image_path)
            add_path(item.thumb_path)

        for item in self.db.scalars(select(VideoClip).where(VideoClip.project_id == project_id)):
            add_path(item.video_path)

        for item in self.db.scalars(select(AudioTrack).where(AudioTrack.project_id == project_id)):
            add_path(item.audio_path)

        for item in self.db.scalars(select(ExportJob).where(ExportJob.project_id == project_id)):
            add_path(item.output_path)

        for item in self.db.scalars(select(Asset).where(Asset.project_id == project_id)):
            add_path(item.cover_image_path)

        for item in self.db.scalars(select(AssetBinding).where(AssetBinding.project_id == project_id)):
            add_path(item.lora_file_path)
            try:
                ref_paths = json.loads(item.reference_image_paths_json or "[]")
            except json.JSONDecodeError:
                ref_paths = []
            for ref_path in ref_paths:
                add_path(str(ref_path))

        for item in self.db.scalars(select(FileRegistry).where(FileRegistry.project_id == project_id)):
            add_path(item.abs_path)

        return file_paths

    def delete_project(self, project: Project) -> dict:
        file_paths = self._collect_project_file_paths(project.id)

        children = [
            AssetBinding,
            AssetVariant,
            AudioTrack,
            VideoClip,
            ExportJob,
            StoryboardFrame,
            FileRegistry,
            TaskQueue,
            Asset,
            ScriptSegment,
        ]
        deleted_rows: dict[str, int] = {}
        for model in children:
            items = list(self.db.scalars(select(model).where(model.project_id == project.id)))
            deleted_rows[model.__tablename__] = len(items)
            for item in items:
                self.db.delete(item)

        self.db.delete(project)
        self.db.commit()

        deleted_file_count = 0
        for path in sorted(file_paths, key=lambda item: len(item.as_posix()), reverse=True):
            try:
                if path.exists() and path.is_file():
                    path.unlink()
                    deleted_file_count += 1
            except Exception:
                continue

        return {
            "project_id": project.id,
            "deleted_files": deleted_file_count,
            "deleted_rows": deleted_rows,
        }
