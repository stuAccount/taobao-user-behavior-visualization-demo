#!/bin/bash
# 启动已有结果的演示仪表盘
set -euo pipefail

streamlit run dashboard/app.py --server.port 8501 --server.address 0.0.0.0 --server.headless true
