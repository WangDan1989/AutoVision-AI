from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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
    for dirname in (
        settings.IMAGES_DIR,
        settings.VIDEOS_DIR,
        settings.AUDIO_DIR,
        settings.EXPORTS_DIR,
        settings.LORAS_DIR,
        settings.TEMP_DIR,
    ):
        (settings.media_root_path / dirname).mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage_dirs()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.APP_NAME, version="0.1.0", lifespan=lifespan)
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
