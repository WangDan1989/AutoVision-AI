import shutil
import subprocess
from pathlib import Path


def run_subprocess(command: list[str], error_prefix: str) -> None:
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        stderr = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"{error_prefix}: {stderr or 'unknown error'}")


def ensure_binary(name: str) -> str:
    if Path(name).exists():
        return str(Path(name).resolve())
    binary_path = shutil.which(name)
    if not binary_path:
        raise RuntimeError(f"未找到可执行文件：{name}")
    return binary_path


def probe_duration(file_path: str) -> float:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0

    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            file_path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return 0.0

    try:
        return round(float((completed.stdout or "0").strip() or 0), 3)
    except ValueError:
        return 0.0


def write_concat_file(target_path: Path, entries: list[str]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(f"file '{Path(item).resolve().as_posix()}'" for item in entries)
    target_path.write_text(content, encoding="utf-8")
