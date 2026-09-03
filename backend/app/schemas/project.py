from typing import Literal

from pydantic import BaseModel, Field


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    aspect_ratio: Literal["16:9", "9:16"] = "16:9"
    target_width: int = 1280
    target_height: int = 720
    fps: int = 24
