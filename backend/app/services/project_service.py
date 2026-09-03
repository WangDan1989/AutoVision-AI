import json

from sqlalchemy.orm import Session

from app.core.enums import ProjectStatus
from app.db.models.project import Project
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
