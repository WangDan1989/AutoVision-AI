from pydantic import BaseModel, Field


class ExportSubtitleItem(BaseModel):
    segment_id: str
    start_sec: float = Field(default=0.0, ge=0.0)
    end_sec: float = Field(default=0.0, ge=0.0)
    text: str = Field(default="")


class GenerateExportRequest(BaseModel):
    subtitle_enabled: bool = Field(default=True)
    transition_enabled: bool = Field(default=True)
    subtitle_items: list[ExportSubtitleItem] = Field(default_factory=list)
