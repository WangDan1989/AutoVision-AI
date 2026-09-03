from pydantic import BaseModel, Field


class ParseScriptRequest(BaseModel):
    raw_script_text: str = Field(min_length=1)


class SegmentItem(BaseModel):
    scene_name: str = ""
    visual_desc: str
    camera_lang: str = ""
    character_ids: list[str] = Field(default_factory=list)
    variant_refs: list[str] = Field(default_factory=list)
    dialogue_text: str = ""
    narration_text: str = ""
    emotion_tags: list[str] = Field(default_factory=list)
