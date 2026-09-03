from pathlib import Path

from app.core.config import settings


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def to_relative_media_path(abs_path: str) -> str:
    path = Path(abs_path).resolve()
    root = settings.media_root_path.resolve()
    return str(path.relative_to(root))
