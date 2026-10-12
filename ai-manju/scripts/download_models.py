from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml


ROOT_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT_DIR / "config.yaml"


def load_config() -> dict:
    with CONFIG_PATH.open("r", encoding="utf-8") as fp:
        return yaml.safe_load(fp)


def ensure_directory(path: str) -> None:
    Path(path).mkdir(parents=True, exist_ok=True)


def set_hf_mirror(config: dict) -> None:
    mirrors = config.get("mirrors", {})
    if mirrors.get("use_hf_mirror"):
        os.environ["HF_ENDPOINT"] = mirrors.get("hf_endpoint", "https://hf-mirror.com")


def resolve_targets(config: dict, only: list[str] | None) -> list[str]:
    if only:
        return only
    return list(config["downloads"].get("default_targets", []))


def download_with_modelscope(model_id: str, local_dir: str) -> None:
    try:
        from modelscope import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "缺少 modelscope，请先执行 `pip install -r requirements.txt`。"
        ) from exc

    snapshot_download(model_id, local_dir=local_dir)


def download_with_huggingface(model_id: str, local_dir: str) -> None:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError(
            "缺少 huggingface_hub，请先执行 `pip install -r requirements.txt`。"
        ) from exc

    snapshot_download(
        repo_id=model_id,
        local_dir=local_dir,
        resume_download=True,
        local_dir_use_symlinks=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="下载 AI 漫剧项目所需模型。")
    parser.add_argument(
        "--only",
        nargs="+",
        help="仅下载指定目标，例如: ref2va_bundle flux_dev chatterbox",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印下载计划，不实际下载。",
    )
    args = parser.parse_args()

    config = load_config()
    set_hf_mirror(config)
    targets = resolve_targets(config, args.only)
    model_map = config["downloads"]["models"]

    if not targets:
        print("未配置默认下载目标，也未传入 --only。", file=sys.stderr)
        return 1

    for target in targets:
        if target not in model_map:
            print(f"未知模型目标: {target}", file=sys.stderr)
            return 1

    print(f"HF_ENDPOINT={os.environ.get('HF_ENDPOINT', '')}")
    for target in targets:
        item = model_map[target]
        source = item["source"]
        model_id = item["model_id"]
        local_dir = item["local_dir"]
        approx_size = item.get("approx_size_gb", "?")

        ensure_directory(local_dir)
        print(f"[PLAN] {target}: {source} | {model_id} -> {local_dir} | ~{approx_size}GB")

        if args.dry_run:
            continue

        if source == "modelscope":
            download_with_modelscope(model_id, local_dir)
        elif source == "huggingface":
            download_with_huggingface(model_id, local_dir)
        else:
            print(f"不支持的下载源: {source}", file=sys.stderr)
            return 1

        print(f"[DONE] {target}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
