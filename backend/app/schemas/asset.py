from pydantic import BaseModel, Field


class BindingRequest(BaseModel):
    binding_mode: str = "LOCAL_LORA"
    lora_enabled: bool = False
    lora_file_path: str = ""
    lora_weight: float = Field(default=0.75, ge=0.0, le=2.0)
    trigger_word: str = ""
    ip_adapter_enabled: bool = False
    ip_adapter_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    reference_image_paths: list[str] = Field(default_factory=list)
    decouple_clothes: bool = True
