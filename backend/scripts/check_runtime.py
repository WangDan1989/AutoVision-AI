#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib import error, request


BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = BACKEND_DIR / ".env"


@dataclass
class CheckResult:
    level: str
    title: str
    detail: str


def load_env_file(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_setting(env_values: dict[str, str], key: str, default: str) -> str:
    return os.getenv(key, env_values.get(key, default))


def add_result(results: list[CheckResult], level: str, title: str, detail: str) -> None:
    results.append(CheckResult(level=level, title=title, detail=detail))


def probe_http(url: str, timeout_sec: float = 3.0) -> tuple[bool, str]:
    req = request.Request(url, method="GET")
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            return True, f"HTTP {resp.status}"
    except error.HTTPError as exc:
        return True, f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def check_python(results: list[CheckResult]) -> None:
    version = sys.version_info
    version_text = f"{version.major}.{version.minor}.{version.micro}"
    if (version.major, version.minor) in {(3, 11), (3, 12), (3, 13)}:
        add_result(results, "ok", "Python 版本", f"当前为 {version_text}，属于推荐版本")
        return
    if version.major == 3 and version.minor >= 14:
        add_result(results, "fail", "Python 版本", f"当前为 {version_text}，后端依赖可能安装失败，建议改用 3.11/3.12/3.13")
        return
    add_result(results, "warn", "Python 版本", f"当前为 {version_text}，建议改用 3.11/3.12/3.13")


def check_env_file(results: list[CheckResult], env_values: dict[str, str]) -> None:
    if ENV_PATH.exists():
        add_result(results, "ok", ".env 配置", f"已检测到 {ENV_PATH}")
    else:
        add_result(results, "fail", ".env 配置", f"未检测到 {ENV_PATH}，请先执行 cp .env.example .env")
    checkpoint = get_setting(env_values, "COMFYUI_CHECKPOINT", "")
    if checkpoint.strip():
        add_result(results, "ok", "ComfyUI Checkpoint", f"当前为 {checkpoint}")
    else:
        add_result(results, "fail", "ComfyUI Checkpoint", "COMFYUI_CHECKPOINT 为空，Step 3 无法真实生成首帧")


def check_storage(results: list[CheckResult], env_values: dict[str, str]) -> None:
    media_root = get_setting(env_values, "MEDIA_ROOT", "./storage")
    media_root_path = Path(media_root)
    if not media_root_path.is_absolute():
        media_root_path = BACKEND_DIR / media_root_path
    if media_root_path.exists():
        add_result(results, "ok", "媒体目录", f"已检测到 {media_root_path}")
    else:
        add_result(results, "warn", "媒体目录", f"未检测到 {media_root_path}，后端启动时会自动创建")


def check_binary(results: list[CheckResult], title: str, binary_name: str, detail_hint: str) -> None:
    binary_path = shutil.which(binary_name)
    if binary_path:
        add_result(results, "ok", title, f"已检测到 {binary_path}")
    else:
        add_result(results, "fail", title, detail_hint)


def check_services(results: list[CheckResult], env_values: dict[str, str]) -> None:
    ollama_base = get_setting(env_values, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_ok, ollama_detail = probe_http(f"{ollama_base}/api/tags")
    if ollama_ok:
        add_result(results, "ok", "Ollama 服务", f"{ollama_base}/api/tags 可访问，{ollama_detail}")
    else:
        add_result(results, "fail", "Ollama 服务", f"无法访问 {ollama_base}/api/tags，请确认已启动 ollama serve；{ollama_detail}")

    comfy_base = get_setting(env_values, "COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    comfy_ok, comfy_detail = probe_http(f"{comfy_base}/system_stats")
    if comfy_ok:
        add_result(results, "ok", "ComfyUI 服务", f"{comfy_base}/system_stats 可访问，{comfy_detail}")
    else:
        add_result(results, "fail", "ComfyUI 服务", f"无法访问 {comfy_base}/system_stats，请确认已启动 ComfyUI Web 服务；{comfy_detail}")

    tts_provider = get_setting(env_values, "TTS_PROVIDER", "edge_tts").strip() or "edge_tts"
    if tts_provider == "http":
        tts_base = get_setting(env_values, "TTS_BASE_URL", "").strip()
        if not tts_base:
            add_result(results, "fail", "HTTP TTS 配置", "TTS_PROVIDER=http 但 TTS_BASE_URL 为空")
        else:
            tts_ok, tts_detail = probe_http(tts_base)
            if tts_ok:
                add_result(results, "ok", "HTTP TTS 服务", f"{tts_base} 可访问，{tts_detail}")
            else:
                add_result(results, "fail", "HTTP TTS 服务", f"无法访问 {tts_base}，请确认本地 HTTP TTS 已启动；{tts_detail}")
    else:
        check_binary(
            results,
            "edge-tts",
            "edge-tts",
            "未检测到 edge-tts，请检查虚拟环境依赖安装，或改用 TTS_PROVIDER=http",
        )


def print_results(results: list[CheckResult]) -> int:
    order = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
    has_fail = False
    for item in results:
        print(f"{order[item.level]} {item.title}: {item.detail}")
        if item.level == "fail":
            has_fail = True
    if has_fail:
        print("\n结论: 当前环境仍有阻断项，建议先修复 FAIL 后再启动真实链路。")
        return 1
    print("\n结论: 当前环境已满足基础联调前置，可继续启动后端和真实服务。")
    return 0


def main() -> int:
    env_values = load_env_file(ENV_PATH)
    results: list[CheckResult] = []
    check_python(results)
    check_env_file(results, env_values)
    check_storage(results, env_values)
    ffmpeg_name = get_setting(env_values, "FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg"
    check_binary(results, "FFmpeg", ffmpeg_name, f"未检测到 {ffmpeg_name}，请检查 FFMPEG_BIN 或确认 ffmpeg 已加入 PATH")
    check_binary(results, "ffprobe", "ffprobe", "未检测到 ffprobe，建议一并安装并加入 PATH")
    check_services(results, env_values)
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
