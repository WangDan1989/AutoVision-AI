from typing import Literal

from pydantic import BaseModel, Field


GENRE_STYLE_CHOICES = Literal[
    "AUTO",
    "GUZHUANG_XIANXIA",
    "GUZHUANG_WUXIA",
    "GUFENG_ZHAIDOU",
    "XIANDAN_DUSHI",
    "XIAOYUAN_QINGCHUN",
    "XUANYI_TUILI",
    "MINGUO_DIEZHAN",
    "KEHUAN_MOSHI",
    "ZHICHANG_JINGYING",
    "JIATING_LUNLI",
    "KAIXIAO_WENNAN",
]

GENRE_STYLE_LABELS: dict[str, str] = {
    "AUTO": "自动识别",
    "GUZHUANG_XIANXIA": "古装仙侠",
    "GUZHUANG_WUXIA": "古装武侠",
    "GUFENG_ZHAIDOU": "古风宅斗",
    "XIANDAN_DUSHI": "现代都市",
    "XIAOYUAN_QINGCHUN": "校园青春",
    "XUANYI_TUILI": "悬疑推理",
    "MINGUO_DIEZHAN": "民国谍战",
    "KEHUAN_MOSHI": "科幻末世",
    "ZHICHANG_JINGYING": "职场经营",
    "JIATING_LUNLI": "家庭伦理",
    "KAIXIAO_WENNAN": "爆笑微甜",
}


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    target_width: int = 1280
    target_height: int = 720
    fps: int = 24
    genre_style: GENRE_STYLE_CHOICES = "AUTO"


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
    storyboard: StoryboardPreferences | None = None
    media: MediaPreferences | None = None
    export: ExportPreferences | None = None


class ConfirmDeleteRequest(BaseModel):
    confirm: bool = False
