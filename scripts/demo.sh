#!/bin/bash
# 阶段 B：基于已有清洗数据和分析结果启动演示仪表盘
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"

if ! "$PYTHON_BIN" - <<'PY'
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
then
    echo "Python 版本需为 3.10+。"
    exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
            apt-get update
            apt-get install -y --no-install-recommends python3-venv
            "$PYTHON_BIN" -m venv "$VENV_DIR"
        else
            echo "创建虚拟环境失败，请安装 python3-venv 后重试。"
            exit 1
        fi
    fi
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
