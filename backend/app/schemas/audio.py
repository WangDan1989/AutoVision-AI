from pydantic import BaseModel, Field


class GenerateAudioRequest(BaseModel):
    track_type: str = Field(default="NARRATION")
    text_content: str = Field(default="")
    voice_profile: str = Field(default="")
