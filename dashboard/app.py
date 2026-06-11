"""Streamlit 仪表盘主入口。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from analysis import config
from analysis.utils import get_cleaned_data_path, load_json


@st.cache_data(show_spinner=False)
def load_overview() -> dict[str, str]:
    """加载首页概览信息。"""
    metrics = {
        "总记录数": "未生成",
        "用户数": "未生成",
        "商品数": "未生成",
        "时间范围": "未生成",
    }

    cleaned_path = None
    try:
        cleaned_path = get_cleaned_data_path()
    except FileNotFoundError:
        return metrics

    if cleaned_path.suffix == ".parquet":
        sample = pd.read_parquet(
            cleaned_path,
            columns=["user_id", "item_id", "datetime"],
        )
    else:
        sample = pd.read_csv(
            cleaned_path,
            usecols=["user_id", "item_id", "datetime"],
            parse_dates=["datetime"],
        )

    if sample.empty:
        return metrics

    metrics["总记录数"] = f"{len(sample):,}"
    metrics["用户数"] = f"{sample['user_id'].nunique():,}"
    metrics["商品数"] = f"{sample['item_id'].nunique():,}"
    metrics["时间范围"] = (
        f"{sample['datetime'].min():%Y-%m-%d} 至 {sample['datetime'].max():%Y-%m-%d}"
    )
    return metrics


def render_status_card(title: str, value: str) -> None:
    """渲染首页状态卡片。"""
    st.metric(title, value)


def main() -> None:
    """渲染仪表盘首页。"""
    st.set_page_config(
        page_title="电商用户行为分析仪表盘",
        page_icon="📊",
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
    st.code(str(Path(config.OUTPUT_DIR)))


if __name__ == "__main__":
    main()
