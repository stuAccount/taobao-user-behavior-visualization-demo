"""行为漏斗分析交互页面。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT_STR = str(PROJECT_ROOT)
if PROJECT_ROOT_STR not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_STR)

from analysis import config
from analysis.utils import load_json, read_table


@st.cache_data(show_spinner=False)
def load_funnel_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """加载漏斗汇总与日趋势。"""
    summary = load_json(config.FUNNEL_SUMMARY_PATH, default={})
    funnel_df = pd.DataFrame(summary.get("funnel", []))
    daily_df = read_table(config.FUNNEL_DAILY_PATH) if config.FUNNEL_DAILY_PATH.exists() else pd.DataFrame()
    return funnel_df, daily_df


st.title("行为漏斗分析")
funnel_df, daily_df = load_funnel_data()

if funnel_df.empty:
    st.warning("尚未生成漏斗结果，请先运行 `python -m analysis.funnel_analysis`。")
    st.stop()

st.plotly_chart(
    px.funnel(funnel_df, x="uv", y="label", title="用户行为漏斗 UV"),
    width="stretch",
)

labels = funnel_df["label"].tolist()
values = [int(min(funnel_df.iloc[index]["uv"], funnel_df.iloc[index + 1]["uv"])) for index in range(len(funnel_df) - 1)]
sankey = go.Figure(
    data=[
        go.Sankey(
            node={"label": labels},
            link={"source": list(range(len(values))), "target": list(range(1, len(values) + 1)), "value": values},
        )
    ]
)
sankey.update_layout(title_text="用户行为转化桑基图")
st.plotly_chart(sankey, width="stretch")

if not daily_df.empty:
    daily_df["date"] = daily_df["date"].astype(str)
    selected_dates = st.multiselect("选择日期", daily_df["date"].tolist(), default=daily_df["date"].tolist())
    filtered_daily = daily_df[daily_df["date"].isin(selected_dates)] if selected_dates else daily_df
    st.plotly_chart(
        px.line(filtered_daily, x="date", y="buy_conversion_rate", markers=True, title="日维度购买转化率趋势"),
        width="stretch",
    )

st.dataframe(funnel_df, width="stretch")
