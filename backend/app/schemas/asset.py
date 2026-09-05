from pydantic import BaseModel, ConfigDict, Field


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


class ConsistencyConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    lock_outfit: bool = False
    face_tags: list[str] = Field(default_factory=list)
    style_lora_name: str = ""
    style_lora_weight: float = 0.0
    style_extra_prompt: str = ""
    scene_anchor_desc: str = ""
    main_camera_tag: str = ""
    lighting_preset: str = ""
    lighting_color_temp_k: int = 0
    lighting_direction: str = ""
    lighting_lut: str = ""
    camera_move_preset: str = ""
    camera_180_axis: str = ""
    pose_tags: dict[str, str] = Field(default_factory=dict)
    voice_preset: str = ""
    voice_emotion_preset: str = ""
    consistency_ref_images: list[str] = Field(default_factory=list)
    scene_ref_images: list[str] = Field(default_factory=list)


class SaveConsistencyRequest(ConsistencyConfig):
    preview_camera_tags: dict[str, str] = Field(default_factory=dict)
    preview_pose_tags: dict[str, str] = Field(default_factory=dict)
    preview_lighting_tags: dict[str, str] = Field(default_factory=dict)
