"""K-Means 聚类分析交互页面。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from analysis import config
from analysis.clustering import assign_clusters, resolve_k, summarize_clusters
from analysis.utils import load_json, read_table


@st.cache_data(show_spinner=False)
def load_cluster_result() -> pd.DataFrame:
    """加载聚类结果。"""
    if not config.CLUSTERING_RESULT_PATH.exists():
        return pd.DataFrame()
    return read_table(config.CLUSTERING_RESULT_PATH)


def build_radar_figure(clustered_df: pd.DataFrame) -> go.Figure:
    """构建交互式雷达图。"""
    metrics = ["recency", "frequency", "monetary"]
    labels = ["R 最近购买", "F 购买频次", "M 购买类目"]
    mean_df = clustered_df.groupby(["cluster", "cluster_label"])[metrics].mean().reset_index()
    scaled = MinMaxScaler().fit_transform(mean_df[metrics]) if len(mean_df) else np.empty((0, 3))
    fig = go.Figure()
    for index, row in mean_df.iterrows():
        values = scaled[index].tolist()
        fig.add_trace(
            go.Scatterpolar(
                r=values + [values[0]],
                theta=labels + [labels[0]],
                fill="toself",
                name=f"{int(row['cluster'])} - {row['cluster_label']}",
            )
        )
    fig.update_layout(title="用户群体画像雷达图", polar={"radialaxis": {"visible": True, "range": [0, 1]}})
    return fig


st.title("K-Means 聚类分析")
cluster_df = load_cluster_result()
summary = load_json(config.CLUSTERING_SUMMARY_PATH, default={})

if cluster_df.empty:
    st.warning("尚未生成聚类结果，请先运行 `python -m analysis.clustering`。")
    st.stop()

k_value = st.slider("选择 K 值", min_value=1, max_value=min(8, len(cluster_df)), value=min(summary.get("selected_k", 3), len(cluster_df)))
feature_df = cluster_df[["user_id", "recency", "frequency", "monetary"]].copy()
features = StandardScaler().fit_transform(feature_df[["recency", "frequency", "monetary"]])
working_df = assign_clusters(feature_df, features, resolve_k(len(feature_df), k_value))
working_summary = summarize_clusters(working_df, pd.DataFrame(summary.get("elbow", [])), resolve_k(len(feature_df), k_value))

cols = st.columns(3)
cols[0].metric("聚类用户数", f"{len(working_df):,}")
cols[1].metric("实际 K 值", working_summary["selected_k"])
cols[2].metric("群体数量", working_summary["cluster_count"])

st.plotly_chart(build_radar_figure(working_df), width="stretch")

if len(working_df) >= 2:
    components = PCA(n_components=2, random_state=config.RANDOM_STATE).fit_transform(features)
    scatter_df = working_df.assign(pca_1=components[:, 0], pca_2=components[:, 1])
    st.plotly_chart(
        px.scatter(scatter_df, x="pca_1", y="pca_2", color="cluster_label", title="PCA 降维聚类散点图"),
        width="stretch",
    )

st.dataframe(pd.DataFrame(working_summary["clusters"]), width="stretch")
