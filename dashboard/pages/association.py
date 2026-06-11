"""Apriori 关联规则交互页面。"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from analysis import config
from analysis.utils import load_json


@st.cache_data(show_spinner=False)
def load_rules() -> pd.DataFrame:
    """加载关联规则结果。"""
    if not config.ASSOCIATION_RULES_PATH.exists():
        return pd.DataFrame()
    return pd.read_csv(config.ASSOCIATION_RULES_PATH)


st.title("Apriori 关联规则")
rules_df = load_rules()
summary = load_json(config.ASSOCIATION_SUMMARY_PATH, default={})

if rules_df.empty:
    st.warning("尚未生成有效关联规则，或当前样本规则为空。")
    st.json(summary or {"提示": "请先运行 `python -m analysis.association_rules`。"})
    st.stop()

support_threshold = st.slider("最小支持度", 0.0, 1.0, float(rules_df["support"].min()), 0.01)
confidence_threshold = st.slider("最小置信度", 0.0, 1.0, float(rules_df["confidence"].min()), 0.01)
filtered_df = rules_df[
    (rules_df["support"] >= support_threshold)
    & (rules_df["confidence"] >= confidence_threshold)
].copy()

st.plotly_chart(
    px.scatter(
        filtered_df,
        x="support",
        y="confidence",
        size="lift",
        color="lift",
        hover_data=["antecedents", "consequents"],
        title="关联规则支持度-置信度分布",
    ),
    width="stretch",
)
st.dataframe(filtered_df, width="stretch")
