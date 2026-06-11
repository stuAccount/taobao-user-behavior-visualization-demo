#!/bin/bash
# 远端默认入口脚本，完整逻辑后续由 setup_and_analyze.sh 承担
set -euo pipefail

bash scripts/setup_and_analyze.sh
