from typing import Literal

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    target_width: int = 1280
    target_height: int = 720
    fps: int = 24


class StoryboardPreferences(BaseModel):
    prompt_override: str = ""
    negative_prompt_override: str = ""
    width: int = Field(default=1280, ge=256)
    height: int = Field(default=720, ge=256)


class MediaPreferences(BaseModel):
    video_duration_sec: int = Field(default=3, ge=1, le=30)
    video_fps: int = Field(default=24, ge=1, le=60)
    video_width: int = Field(default=1280, ge=256)
    video_height: int = Field(default=720, ge=256)
    audio_track_type: str = "NARRATION"
    audio_voice_profile: str = ""


class ExportPreferences(BaseModel):
    subtitle_enabled: bool = True
    transition_enabled: bool = True


class ProjectPreferences(BaseModel):
    storyboard: StoryboardPreferences = Field(default_factory=StoryboardPreferences)
    media: MediaPreferences = Field(default_factory=MediaPreferences)
    export: ExportPreferences = Field(default_factory=ExportPreferences)


class UpdateProjectPreferencesRequest(BaseModel):
    preferences: ProjectPreferences
