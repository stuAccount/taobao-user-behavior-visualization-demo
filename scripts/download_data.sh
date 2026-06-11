#!/bin/bash
# 独立数据下载脚本，优先使用 Kaggle API
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
DATA_DIR="$PROJECT_ROOT/data"
RAW_FILE="$DATA_DIR/UserBehavior.csv"

mkdir -p "$DATA_DIR"

if [ -f "$RAW_FILE" ]; then
    SIZE="$(du -h "$RAW_FILE" | cut -f1)"
    echo "数据文件已存在：data/UserBehavior.csv（${SIZE}），跳过下载。"
    exit 0
fi

echo "开始下载 UserBehavior 数据集（约 3.67GB）。"

if command -v kaggle >/dev/null 2>&1 || [ -n "${KAGGLE_USERNAME:-}" ] || [ -f "$HOME/.kaggle/kaggle.json" ]; then
    "$PYTHON_BIN" -m pip install -q kaggle
    if command -v kaggle >/dev/null 2>&1; then
        KAGGLE_CMD="kaggle"
    else
        KAGGLE_CMD="$PROJECT_ROOT/.venv/bin/kaggle"
    fi
    "$KAGGLE_CMD" datasets download -d gogokerry/taobao-user-behavior -p "$DATA_DIR" --unzip
else
    echo "未检测到 Kaggle 凭据，尝试 Kaggle 公共下载接口。"
    curl -L -o "$DATA_DIR/taobao-user-behavior.zip" \
        "https://www.kaggle.com/api/v1/datasets/download/gogokerry/taobao-user-behavior"
    unzip -o "$DATA_DIR/taobao-user-behavior.zip" -d "$DATA_DIR"
    rm -f "$DATA_DIR/taobao-user-behavior.zip"
fi

if [ ! -f "$RAW_FILE" ]; then
    FOUND_FILE="$(find "$DATA_DIR" -maxdepth 2 -type f -iname '*UserBehavior*.csv' | head -n 1 || true)"
    if [ -n "$FOUND_FILE" ]; then
        mv "$FOUND_FILE" "$RAW_FILE"
    fi
fi

if [ -f "$RAW_FILE" ]; then
    LINES="$(wc -l < "$RAW_FILE" | tr -d ' ')"
    SIZE="$(du -h "$RAW_FILE" | cut -f1)"
    echo "数据下载完成：data/UserBehavior.csv（${LINES} 行，${SIZE}）。"
else
    echo "下载后未找到 data/UserBehavior.csv。"
    echo "请确认 Kaggle API 已配置：KAGGLE_USERNAME / KAGGLE_KEY 或 ~/.kaggle/kaggle.json。"
    echo "也可以手动下载后放到 data/UserBehavior.csv。"
    find "$DATA_DIR" -maxdepth 2 -type f -print
    exit 1
fi
