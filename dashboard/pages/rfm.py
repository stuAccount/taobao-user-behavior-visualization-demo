"""RFM 分析交互页面。"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import config
from analysis.rfm_analysis import score_rfm_table, summarize_rfm
from analysis.utils import load_json, read_table


@st.cache_data(show_spinner=False)
def load_rfm_result() -> pd.DataFrame:
    """加载 RFM 结果。"""
    if not config.RFM_RESULT_PATH.exists():
        return pd.DataFrame()
    return read_table(config.RFM_RESULT_PATH)


st.title("RFM 用户价值分析")
rfm_df = load_rfm_result()
summary = load_json(config.RFM_SUMMARY_PATH, default={})

if rfm_df.empty:
    st.warning("尚未生成 RFM 结果，请先运行 `python -m analysis.rfm_analysis`。")
    st.stop()

recency_adjust = st.slider("R 阈值微调天数", min_value=-5, max_value=5, value=0, step=1)
working_df = rfm_df.copy()
if recency_adjust:
    working_df["recency"] = (working_df["recency"] + recency_adjust).clip(lower=0)
    working_df = score_rfm_table(working_df)
    summary = summarize_rfm(working_df)

metric_cols = st.columns(3)
metric_cols[0].metric("购买用户数", f"{summary.get('total_buy_users', len(working_df)):,}")
metric_cols[1].metric("平均购买次数", f"{working_df['frequency'].mean():.2f}")
metric_cols[2].metric("平均购买类目数", f"{working_df['monetary'].mean():.2f}")

segment_counts = working_df["segment"].value_counts().reset_index()
segment_counts.columns = ["用户分层", "用户数"]
st.plotly_chart(
    px.pie(segment_counts, names="用户分层", values="用户数", hole=0.45, title="用户分层占比"),
    width="stretch",
)

mean_df = working_df.groupby("segment")[["recency", "frequency", "monetary"]].mean().reset_index()
st.plotly_chart(
    px.bar(mean_df, x="segment", y=["recency", "frequency", "monetary"], barmode="group", title="各分层 RFM 均值对比"),
    width="stretch",
)

st.dataframe(working_df.sort_values(["segment", "frequency"], ascending=[True, False]).head(200), width="stretch")
