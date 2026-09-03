#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
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


def probe_http_json(url: str, timeout_sec: float = 5.0) -> tuple[bool, str, object | None]:
    req = request.Request(url, method="GET", headers={"Accept": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout_sec) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            parsed = json.loads(body) if body else None
            return True, f"HTTP {resp.status}", parsed
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return True, f"HTTP {exc.code}", parsed
    except Exception as exc:  # noqa: BLE001
        return False, str(exc), None


def run_command(command: list[str], timeout_sec: float = 8.0) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    output = (completed.stdout or completed.stderr or "").strip()
    if completed.returncode != 0:
        return False, output or f"exit code {completed.returncode}"
    return True, output


def check_ffmpeg(results: list[CheckResult], env_values: dict[str, str]) -> None:
    ffmpeg_name = get_setting(env_values, "FFMPEG_BIN", "ffmpeg").strip() or "ffmpeg"
    ffmpeg_path = shutil.which(ffmpeg_name) or (ffmpeg_name if Path(ffmpeg_name).exists() else "")
    if not ffmpeg_path:
        add_result(results, "fail", "FFmpeg", f"未检测到 {ffmpeg_name}，请检查 FFMPEG_BIN 或确认 ffmpeg 已加入 PATH")
        return
    add_result(results, "ok", "FFmpeg", f"已检测到 {ffmpeg_path}")

    ok, output = run_command([ffmpeg_path, "-version"])
    if ok:
        first_line = output.splitlines()[0] if output else "ffmpeg -version 执行成功"
        add_result(results, "ok", "FFmpeg 版本", first_line)
    else:
        add_result(results, "fail", "FFmpeg 版本", f"执行 ffmpeg -version 失败: {output}")

    ok, output = run_command([ffmpeg_path, "-filters"], timeout_sec=12.0)
    if not ok:
        add_result(results, "warn", "FFmpeg 字幕过滤器", f"执行 ffmpeg -filters 失败，无法确认 subtitles 过滤器: {output}")
        return
    if "subtitles" in output:
        add_result(results, "ok", "FFmpeg 字幕过滤器", "已检测到 subtitles 过滤器，支持 Step 5 字幕烧录")
    else:
        add_result(results, "fail", "FFmpeg 字幕过滤器", "未检测到 subtitles 过滤器，Step 5 字幕烧录可能失败")


def check_ollama(results: list[CheckResult], env_values: dict[str, str]) -> None:
    ollama_base = get_setting(env_values, "OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_model = get_setting(env_values, "OLLAMA_MODEL", "qwen2.5:14b").strip() or "qwen2.5:14b"
    ok, detail, payload = probe_http_json(f"{ollama_base}/api/tags")
    if not ok:
        add_result(results, "fail", "Ollama 服务", f"无法访问 {ollama_base}/api/tags，请确认已启动 ollama serve；{detail}")
        return
    add_result(results, "ok", "Ollama 服务", f"{ollama_base}/api/tags 可访问，{detail}")
    models = payload.get("models", []) if isinstance(payload, dict) else []
    names = {str(item.get('name', '')).strip() for item in models if isinstance(item, dict)}
    if ollama_model in names:
        add_result(results, "ok", "Ollama 模型", f"已检测到模型 {ollama_model}")
    else:
        add_result(results, "fail", "Ollama 模型", f"未检测到模型 {ollama_model}，请先执行 ollama pull {ollama_model}")


def check_comfyui(results: list[CheckResult], env_values: dict[str, str]) -> None:
    comfy_base = get_setting(env_values, "COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")
    checkpoint = get_setting(env_values, "COMFYUI_CHECKPOINT", "").strip()
    if not checkpoint:
        add_result(results, "fail", "ComfyUI Checkpoint", "COMFYUI_CHECKPOINT 为空，Step 3 无法真实生成首帧")
    else:
        add_result(results, "ok", "ComfyUI Checkpoint", f"当前为 {checkpoint}")

    ok, detail, payload = probe_http_json(f"{comfy_base}/system_stats")
    if not ok:
        add_result(results, "fail", "ComfyUI 服务", f"无法访问 {comfy_base}/system_stats，请确认已启动 ComfyUI Web 服务；{detail}")
        return
    add_result(results, "ok", "ComfyUI 服务", f"{comfy_base}/system_stats 可访问，{detail}")
    if isinstance(payload, dict) and payload:
        add_result(results, "ok", "ComfyUI 状态", "system_stats 返回了有效 JSON")
    else:
        add_result(results, "warn", "ComfyUI 状态", "system_stats 可访问，但返回内容为空或非预期")


def check_tts(results: list[CheckResult], env_values: dict[str, str]) -> None:
    provider = get_setting(env_values, "TTS_PROVIDER", "edge_tts").strip() or "edge_tts"
    if provider == "http":
        tts_base = get_setting(env_values, "TTS_BASE_URL", "").strip()
        if not tts_base:
            add_result(results, "fail", "HTTP TTS 配置", "TTS_PROVIDER=http 但 TTS_BASE_URL 为空")
            return
        ok, detail, _ = probe_http_json(tts_base)
        if ok:
            add_result(results, "ok", "HTTP TTS 服务", f"{tts_base} 可访问，{detail}")
        else:
            add_result(results, "fail", "HTTP TTS 服务", f"无法访问 {tts_base}，请确认本地 HTTP TTS 已启动；{detail}")
        return

    binary_path = shutil.which("edge-tts")
    if not binary_path:
        add_result(results, "fail", "edge-tts", "未检测到 edge-tts，请检查虚拟环境依赖安装，或改用 TTS_PROVIDER=http")
        return
    add_result(results, "ok", "edge-tts", f"已检测到 {binary_path}")
    ok, output = run_command([binary_path, "--list-voices"], timeout_sec=15.0)
    if ok and output:
        preview = output.splitlines()[0]
        add_result(results, "ok", "edge-tts 语音列表", f"已成功获取语音列表，示例: {preview}")
    else:
        add_result(results, "warn", "edge-tts 语音列表", f"获取语音列表失败，可能是网络或服务限制: {output}")


def print_results(results: list[CheckResult]) -> int:
    prefix = {"ok": "[OK]", "warn": "[WARN]", "fail": "[FAIL]"}
    has_fail = False
    for item in results:
        print(f"{prefix[item.level]} {item.title}: {item.detail}")
        if item.level == "fail":
            has_fail = True
    if has_fail:
        print("\n结论: 服务级 smoke test 仍有阻断项，真实链路暂不建议直接开跑。")
        return 1
    print("\n结论: 服务级 smoke test 已通过，真实依赖已具备基础工作条件。")
    return 0


def main() -> int:
    env_values = load_env_file(ENV_PATH)
    results: list[CheckResult] = []
    check_ffmpeg(results, env_values)
    check_ollama(results, env_values)
    check_comfyui(results, env_values)
    check_tts(results, env_values)
    return print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())
