from pydantic import BaseModel, Field


class GenerateFrameRequest(BaseModel):
    prompt_override: str = ""
    negative_prompt_override: str = ""
    width: int = Field(default=1280, ge=256)
    height: int = Field(default=720, ge=256)


class LockFrameRequest(BaseModel):
    is_locked: bool = True
