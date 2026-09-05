from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "AutoVision-AI"
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    SQLITE_PATH: str = "./autovision.db"

    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"
    OLLAMA_TIMEOUT_SEC: int = 180
    COMFYUI_BASE_URL: str = "http://127.0.0.1:8188"
    COMFYUI_CHECKPOINT: str = ""
    COMFYUI_NEGATIVE_PROMPT: str = "low quality, blurry, bad anatomy, extra fingers, deformed face"
    COMFYUI_PIPELINE: str = "Z_IMAGE_TURBO"
    COMFYUI_Z_UNET: str = "z_image_turbo_bf16.safetensors"
    COMFYUI_Z_CLIP: str = "qwen_3_4b.safetensors"
    COMFYUI_Z_VAE: str = "ae.safetensors"
    COMFYUI_Z_SIGMA: int = 3
    COMFYUI_Z_STEPS: int = 8
    COMFYUI_Z_CFG: float = 1.0
    COMFYUI_Z_SAMPLER: str = "res_multistep"
    COMFYUI_Z_SCHEDULER: str = "simple"
    TTS_BASE_URL: str = ""
    TTS_PROVIDER: str = "edge_tts"
    TTS_VOICE: str = "zh-CN-XiaoxiaoNeural"
    FFMPEG_BIN: str = "ffmpeg"
    DEFAULT_VIDEO_DURATION_SEC: int = 3
    EXPORT_TRANSITION_SEC: float = 0.35

    MEDIA_ROOT: str = "./storage"
    IMAGES_DIR: str = "images"
    VIDEOS_DIR: str = "videos"
    AUDIO_DIR: str = "audio"
    EXPORTS_DIR: str = "exports"
    LORAS_DIR: str = "loras"
    TEMP_DIR: str = "temp"

    DEFAULT_WIDTH: int = 1280
    DEFAULT_HEIGHT: int = 720
    DEFAULT_FPS: int = 24
    DEFAULT_ASPECT_RATIO: str = "16:9"

    @property
    def sqlite_url(self) -> str:
        db_path = Path(self.SQLITE_PATH)
        if not db_path.is_absolute():
            db_path = BACKEND_DIR / db_path
        return f"sqlite:///{db_path}"

    @property
    def media_root_path(self) -> Path:
        media_root = Path(self.MEDIA_ROOT)
        if not media_root.is_absolute():
            media_root = BACKEND_DIR / media_root
        return media_root


settings = Settings()
