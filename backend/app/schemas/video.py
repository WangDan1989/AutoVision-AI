from pydantic import BaseModel, Field


class GenerateVideoRequest(BaseModel):
    duration_sec: int = Field(default=3, ge=1, le=30)
    fps: int = Field(default=24, ge=1, le=60)
    width: int = Field(default=1280, ge=256)
    height: int = Field(default=720, ge=256)
