from contextlib import asynccontextmanager
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent
_LIBS_DIR = _BACKEND_DIR / "libs"
for _p in (str(_BACKEND_DIR), str(_LIBS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes.audio import router as audio_router
from app.api.routes.assets import router as assets_router
from app.api.routes.exports import router as exports_router
from app.api.routes.projects import router as projects_router
from app.api.routes.script import router as script_router
from app.api.routes.storyboard import router as storyboard_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.uploads import router as uploads_router
from app.api.routes.video import router as video_router
from app.core.config import settings
from app.db.base import Base
from app.db.session import engine


def ensure_storage_dirs() -> None:
    settings.media_root_path.mkdir(parents=True, exist_ok=True)
    for dirname in (
        settings.IMAGES_DIR,
        settings.VIDEOS_DIR,
        settings.AUDIO_DIR,
        settings.EXPORTS_DIR,
        settings.LORAS_DIR,
        settings.TEMP_DIR,
    ):
        (settings.media_root_path / dirname).mkdir(parents=True, exist_ok=True)


def ensure_runtime_columns() -> None:
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(projects)")).mappings().all()
        columns = {row["name"] for row in rows}
        if "preferences_json" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN preferences_json TEXT NOT NULL DEFAULT '{}'"
                )
            )
        if "genre_style" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN genre_style TEXT NOT NULL DEFAULT 'AUTO'"
                )
            )
        if "last_parse_result_json" not in columns:
            conn.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN last_parse_result_json TEXT NOT NULL DEFAULT '{}'"
                )
            )
        seg_rows = conn.execute(text("PRAGMA table_info(script_segments)")).mappings().all()
        seg_cols = {row["name"] for row in seg_rows}
        if "location_canonical" not in seg_cols:
            conn.execute(
                text(
                    "ALTER TABLE script_segments ADD COLUMN location_canonical TEXT NOT NULL DEFAULT ''"
                )
            )
        asset_rows = conn.execute(text("PRAGMA table_info(assets)")).mappings().all()
        asset_cols = {row["name"] for row in asset_rows}
        if "consistency_config_json" not in asset_cols:
            conn.execute(
                text(
                    "ALTER TABLE assets ADD COLUMN consistency_config_json TEXT NOT NULL DEFAULT '{}'"
                )
            )
        preview_rows = conn.execute(text("PRAGMA table_info(asset_previews)")).mappings().all()
        preview_cols = {row["name"] for row in preview_rows}
        if "camera_tag" not in preview_cols:
            conn.execute(
                text(
                    "ALTER TABLE asset_previews ADD COLUMN camera_tag TEXT NOT NULL DEFAULT ''"
                )
            )
        if "pose_tag" not in preview_cols:
            conn.execute(
                text(
                    "ALTER TABLE asset_previews ADD COLUMN pose_tag TEXT NOT NULL DEFAULT ''"
                )
            )
        if "lighting_tag" not in preview_cols:
            conn.execute(
                text(
                    "ALTER TABLE asset_previews ADD COLUMN lighting_tag TEXT NOT NULL DEFAULT ''"
                )
            )


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_dirs()
    Base.metadata.create_all(bind=engine)
    ensure_runtime_columns()
    yield


ensure_storage_dirs()

app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", StaticFiles(directory=str(settings.media_root_path)), name="media")

app.include_router(projects_router)
app.include_router(script_router)
app.include_router(assets_router)
app.include_router(storyboard_router)
app.include_router(video_router)
app.include_router(audio_router)
app.include_router(exports_router)
app.include_router(tasks_router)
app.include_router(uploads_router)


@app.get("/healthz")
def healthz():
    return {"ok": True}
