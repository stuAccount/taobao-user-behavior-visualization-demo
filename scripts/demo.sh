#!/bin/bash
# 阶段 B：基于已有清洗数据和分析结果启动演示仪表盘
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if [ ! -d "$VENV_DIR" ]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PYTHON="$PROJECT_ROOT/$VENV_DIR/bin/python"
STREAMLIT="$PROJECT_ROOT/$VENV_DIR/bin/streamlit"

echo "========== 安装依赖 =========="
"$PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

if [ ! -d data/cleaned ]; then
    echo "未找到 data/cleaned/ 目录。"
    echo "请先运行 ./run.sh，或解压已有结果：tar -xzf results_bundle.tar.gz"
    exit 1
fi

echo "========== 启动 Streamlit 仪表盘 =========="
"$STREAMLIT" run dashboard/app.py \
    --server.port "${STREAMLIT_PORT:-8501}" \
    --server.address "${STREAMLIT_ADDRESS:-0.0.0.0}" \
    --server.headless true
