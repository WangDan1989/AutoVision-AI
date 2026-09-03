from typing import Any

from pydantic import BaseModel, Field


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: dict[str, Any] = Field(default_factory=dict)
    request_id: str
