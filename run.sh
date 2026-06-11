#!/bin/bash
# 远端默认入口脚本：执行完整数据下载、清洗与分析流程
set -euo pipefail

bash scripts/setup_and_analyze.sh
