"""Streamlit 仪表盘主入口。"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT_STR = str(PROJECT_ROOT)
if PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_STR)

from analysis import config
from analysis.utils import load_json


@st.cache_data(show_spinner=False)
def load_overview() -> dict[str, str]:
    """加载首页概览信息。"""
    summary = load_json(config.CLEANING_SUMMARY_PATH, default={})
    if summary:
        date_range = summary.get("date_range", {})
        start = str(date_range.get("start", "未知"))[:10]
        end = str(date_range.get("end", "未知"))[:10]
        return {
            "总记录数": f"{summary.get('final_rows', 0):,}",
            "用户数": f"{summary.get('user_count', 0):,}",
            "商品数": f"{summary.get('item_count', 0):,}",
            "时间范围": f"{start} 至 {end}",
        }

    metrics = {
        "总记录数": "未生成",
        "用户数": "未生成",
        "商品数": "未生成",
        "时间范围": "未生成",
    }
    return metrics


def render_status_card(title: str, value: str) -> None:
    """渲染首页状态卡片。"""
    st.metric(title, value)


def main() -> None:
    """渲染仪表盘首页。"""
    st.set_page_config(
        page_title="电商用户行为分析仪表盘",
        page_icon="bar_chart",
        layout="wide",
    )
    st.title("电商用户行为分析仪表盘")
    st.caption("基于淘宝 UserBehavior 数据集的课程汇报演示系统")

    st.info(
        "请先运行 `python -m analysis.data_cleaning` 和各分析模块生成结果，"
        "再使用侧边栏进入详细页面。"
    )

    metrics = load_overview()
    cols = st.columns(4)
    for col, (title, value) in zip(cols, metrics.items()):
        with col:
            render_status_card(title, value)

    summary = load_json(config.CLEANING_SUMMARY_PATH, default={})
    if summary:
        st.subheader("最近一次数据清洗摘要")
        st.json(summary)

    st.subheader("结果文件位置")
    st.code(str(config.OUTPUT_DIR))


if __name__ == "__main__":
    main()
