from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.yaml"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def result_line(status: str, title: str, detail: str) -> str:
    return f"[{status}] {title}: {detail}"


def check_python(config: dict) -> tuple[bool, str]:
    required = tuple(int(v) for v in config["environment"]["python_min_version"].split("."))
    current = sys.version_info[:2]
    ok = current >= required
    return ok, result_line("OK" if ok else "FAIL", "Python", f"{current[0]}.{current[1]} >= {required[0]}.{required[1]}")


def check_disk(config: dict) -> tuple[bool, str]:
    model_dir = Path(config["paths"]["model_dir"])
    usage = shutil.disk_usage(model_dir)
    free_gb = usage.free / (1024 ** 3)
    required_gb = config["environment"]["ref2va_min_free_disk_gb"]
    ok = free_gb >= required_gb
    return ok, result_line("OK" if ok else "FAIL", "磁盘空间", f"剩余 {free_gb:.1f} GiB, 要求 >= {required_gb} GiB")


def check_proxy() -> tuple[bool, str]:
    proxy = (
        os_environ("HTTPS_PROXY")
        or os_environ("https_proxy")
        or os_environ("HTTP_PROXY")
        or os_environ("http_proxy")
    )
    ok = bool(proxy)
    detail = proxy if proxy else "未检测到代理环境变量，可继续但下载可能更慢"
    return ok, result_line("OK" if ok else "WARN", "代理", detail)


def os_environ(name: str) -> str:
    import os

    return os.environ.get(name, "")


def check_hf_endpoint(config: dict) -> tuple[bool, str]:
    import os

    expected = config["mirrors"]["hf_endpoint"]
    actual = os.environ.get("HF_ENDPOINT", "")
    if not actual:
        return True, result_line("WARN", "HF_ENDPOINT", f"未设置，建议使用 {expected}")

    ok = actual == expected
    detail = actual
    return ok, result_line("OK" if ok else "WARN", "HF_ENDPOINT", detail)


def check_nvidia_smi(config: dict) -> tuple[bool, str]:
    if not config["environment"].get("require_nvidia_smi", True):
        return True, result_line("OK", "GPU 检查", "配置中未强制要求 nvidia-smi")

    binary = shutil.which("nvidia-smi")
    if not binary:
        return False, result_line("FAIL", "nvidia-smi", "未找到命令，无法确认 GPU 状态")

    try:
        completed = subprocess.run(
            [binary, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"],
            check=True,
            capture_output=True,
            text=True,
        )
        detail = completed.stdout.strip() or "命令执行成功"
        return True, result_line("OK", "GPU", detail)
    except subprocess.CalledProcessError as exc:
        return False, result_line("FAIL", "GPU", exc.stderr.strip() or "nvidia-smi 执行失败")


def check_ref2va_dir(config: dict) -> tuple[bool, str]:
    model_dir = Path(config["downloads"]["models"]["ref2va_bundle"]["local_dir"])
    if not model_dir.exists():
        return True, result_line("WARN", "Ref2VA 目录", f"目录不存在: {model_dir}")

    has_files = any(model_dir.iterdir())
    if not has_files:
        return True, result_line("WARN", "Ref2VA 目录", f"目录存在但仍为空: {model_dir}")

    return True, result_line("OK", "Ref2VA 目录", str(model_dir))


def check_platform() -> tuple[bool, str]:
    detail = f"{platform.system()} {platform.release()}"
    return True, result_line("OK", "平台", detail)


def main() -> int:
    config = load_config()
    checks = [
        check_platform(),
        check_python(config),
        check_disk(config),
        check_proxy(),
        check_hf_endpoint(config),
        check_nvidia_smi(config),
        check_ref2va_dir(config),
    ]

    has_failure = False
    for ok, line in checks:
        print(line)
        if not ok and "[FAIL]" in line:
            has_failure = True

    if has_failure:
        print("\n结论: Ref2VA 下载 / 运行前条件未全部满足，请先处理 FAIL 项。")
        return 1

    print("\n结论: 第一轮下载与环境准备项可继续推进。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
