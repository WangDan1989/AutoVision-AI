from pydantic import BaseModel, Field


class GenerateExportRequest(BaseModel):
    subtitle_enabled: bool = Field(default=True)
    transition_enabled: bool = Field(default=True)
