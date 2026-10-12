#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"

mkdir -p \
  "$ROOT_DIR/data/novel_index" \
  "$ROOT_DIR/models" \
  "$ROOT_DIR/uploads/frames" \
  "$ROOT_DIR/uploads/videos" \
  "$ROOT_DIR/uploads/audio" \
  "$ROOT_DIR/output" \
  "$ROOT_DIR/logs"

echo "HF_ENDPOINT=$HF_ENDPOINT"
echo "项目目录已初始化: $ROOT_DIR"
echo "下一步可执行:"
echo "  python3 -m venv .venv"
echo "  source .venv/bin/activate"
echo "  pip install -r requirements.txt"
echo "  python scripts/validate_ref2va_env.py"
echo "  python scripts/download_models.py --only ref2va_bundle"
