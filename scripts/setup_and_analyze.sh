#!/bin/bash
# 阶段 A：完整下载、清洗、分析与打包流程
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
RUN_APRIORI="${RUN_APRIORI:-0}"
CLEANING_THREADS="${CLEANING_THREADS:-64}"
export CLEANING_ENGINE="${CLEANING_ENGINE:-polars}"
export POLARS_MAX_THREADS="${POLARS_MAX_THREADS:-$CLEANING_THREADS}"

install_ubuntu_packages_if_possible() {
    if command -v apt-get >/dev/null 2>&1 && [ "$(id -u)" = "0" ]; then
        echo "检测到 Ubuntu/Debian root 环境，安装系统依赖。"
        apt-get update
        apt-get install -y --no-install-recommends python3-venv curl unzip
    fi
}

echo "========== [1/6] 检查 Python 环境 =========="
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "未找到 Python，请先安装 Python 3.10+。"
    exit 1
fi

PYTHON_CHECK="$($PYTHON_BIN - <<'PY'
import sys
print(f"{sys.version_info.major}.{sys.version_info.minor}")
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
)" || {
    echo "当前 Python 版本低于 3.10：$PYTHON_CHECK"
    exit 1
}
echo "当前 Python 版本：$PYTHON_CHECK"

install_ubuntu_packages_if_possible

if [ ! -d "$VENV_DIR" ]; then
    echo "创建虚拟环境：$VENV_DIR"
    if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        install_ubuntu_packages_if_possible
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    fi
fi

PYTHON="$PROJECT_ROOT/$VENV_DIR/bin/python"

echo "========== [2/6] 安装 Python 依赖 =========="
"$PYTHON" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r requirements.txt

echo "========== [3/6] 检查并下载数据 =========="
bash scripts/download_data.sh

echo "========== [4/6] 数据清洗 =========="
echo "清洗引擎：$CLEANING_ENGINE，Polars 线程数：$POLARS_MAX_THREADS"
"$PYTHON" -m analysis.data_cleaning

echo "========== [5/6] 运行分析模块 =========="
"$PYTHON" -m analysis.rfm_analysis
"$PYTHON" -m analysis.funnel_analysis
"$PYTHON" -m analysis.clustering

if [ "$RUN_APRIORI" = "1" ]; then
    echo "========== [5/6] 运行 Apriori 关联规则（可选） =========="
    if ! "$PYTHON" -m analysis.association_rules; then
        echo "Apriori 模块执行失败，核心分析结果已生成；可调低阈值或关闭 RUN_APRIORI 后重试。"
    fi
else
    echo "跳过 Apriori：如需启用，请执行 RUN_APRIORI=1 ./run.sh"
fi

echo "========== [6/6] 打包结果 =========="
tar -czf results_bundle.tar.gz output/ data/cleaned/

echo "全部完成。"
echo "结果包：$PROJECT_ROOT/results_bundle.tar.gz"
echo "启动仪表盘：bash scripts/demo.sh"
