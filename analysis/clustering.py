"""K-Means 用户聚类分析模块。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from analysis import config
from analysis.rfm_analysis import build_rfm_table
from analysis.utils import (
    ensure_directories,
    get_logger,
    load_cleaned_data,
    log_step,
    read_table,
    save_dataframe,
    save_json,
)
from analysis.visualization import configure_matplotlib, create_figure, radar_angles, save_figure


def load_or_build_rfm() -> pd.DataFrame:
    """加载或构建 RFM 数据。"""
    if config.RFM_RESULT_PATH.exists():
        return read_table(config.RFM_RESULT_PATH)
    df = load_cleaned_data(columns=["user_id", "item_id", "category_id", "behavior", "datetime"])
    return build_rfm_table(df)


def prepare_features(rfm: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """准备聚类特征。"""
    feature_columns = ["recency", "frequency", "monetary"]
    feature_df = rfm[["user_id", *feature_columns]].dropna().copy()
    if feature_df.empty:
        return feature_df, np.empty((0, len(feature_columns)))
    scaler = StandardScaler()
    features = scaler.fit_transform(feature_df[feature_columns])
    return feature_df, features


def resolve_k(sample_count: int, requested_k: int = config.KMEANS_OPTIMAL_K) -> int:
    """根据样本数修正 K 值。"""
    if sample_count <= 1:
        return 1
    return max(2, min(requested_k, sample_count))


def calculate_elbow(features: np.ndarray) -> pd.DataFrame:
    """计算肘部法则 SSE。"""
    sample_count = len(features)
    if sample_count < 2:
        return pd.DataFrame(columns=["k", "inertia"])

    min_k, max_k = config.KMEANS_K_RANGE
    max_k = min(max_k, sample_count)
    rows = []
    for k in range(min_k, max_k + 1):
        model = KMeans(n_clusters=k, random_state=config.RANDOM_STATE, n_init="auto")
        model.fit(features)
        rows.append({"k": k, "inertia": float(model.inertia_)})
    return pd.DataFrame(rows)


def assign_clusters(feature_df: pd.DataFrame, features: np.ndarray, k: int) -> pd.DataFrame:
    """执行 K-Means 聚类并返回结果。"""
    result = feature_df.copy()
    if result.empty:
        result["cluster"] = pd.Series(dtype="int8")
        result["cluster_label"] = pd.Series(dtype="object")
        return result
    if k == 1:
        result["cluster"] = 0
    else:
        model = KMeans(n_clusters=k, random_state=config.RANDOM_STATE, n_init="auto")
        result["cluster"] = model.fit_predict(features)
    result["cluster_label"] = build_cluster_labels(result)
    return result


def build_cluster_labels(clustered_df: pd.DataFrame) -> pd.Series:
    """根据群体特征生成中文画像标签。"""
    if clustered_df.empty:
        return pd.Series(dtype="object")

    means = clustered_df.groupby("cluster")[["recency", "frequency", "monetary"]].mean()
    frequency_rank = means["frequency"].rank(method="dense", ascending=False)
    recency_rank = means["recency"].rank(method="dense", ascending=True)
    monetary_rank = means["monetary"].rank(method="dense", ascending=False)

    labels = {}
    for cluster_id in means.index:
        if frequency_rank[cluster_id] == 1 and monetary_rank[cluster_id] == 1:
            labels[cluster_id] = "高价值高活跃群体"
        elif recency_rank[cluster_id] == 1:
            labels[cluster_id] = "近期活跃潜力群体"
        elif frequency_rank[cluster_id] >= len(means):
            labels[cluster_id] = "低频沉默群体"
        else:
            labels[cluster_id] = "稳定发展群体"
    return clustered_df["cluster"].map(labels)


def summarize_clusters(clustered_df: pd.DataFrame, elbow_df: pd.DataFrame, k: int) -> dict[str, object]:
    """生成聚类分析摘要。"""
    if clustered_df.empty:
        return {"cluster_count": 0, "selected_k": k, "clusters": {}, "elbow": []}
    summary_df = (
        clustered_df.groupby(["cluster", "cluster_label"])[["user_id", "recency", "frequency", "monetary"]]
        .agg(user_count=("user_id", "count"), recency=("recency", "mean"), frequency=("frequency", "mean"), monetary=("monetary", "mean"))
        .reset_index()
    )
    summary_df["user_ratio"] = (summary_df["user_count"] / summary_df["user_count"].sum() * 100).round(2)
    return {
        "cluster_count": int(clustered_df["cluster"].nunique()),
        "selected_k": int(k),
        "clusters": summary_df.round(2).to_dict(orient="records"),
        "elbow": elbow_df.round(4).to_dict(orient="records"),
    }


def plot_elbow(elbow_df: pd.DataFrame) -> None:
    """绘制肘部法则图。"""
    if elbow_df.empty:
        return
    fig, ax = create_figure()
    ax.plot(elbow_df["k"], elbow_df["inertia"], marker="o", color=config.COLORS["secondary"])
    ax.set_title("K-Means 肘部法则")
    ax.set_xlabel("K 值")
    ax.set_ylabel("SSE")
    save_figure(fig, config.CLUSTERING_OUTPUT_DIR / "clustering_elbow.png")


def plot_radar(clustered_df: pd.DataFrame) -> None:
    """绘制聚类群体画像雷达图。"""
    if clustered_df.empty or clustered_df["cluster"].nunique() < 1:
        return
    configure_matplotlib()
    metrics = ["recency", "frequency", "monetary"]
    labels = ["R 最近购买", "F 购买频次", "M 购买类目"]
    mean_df = clustered_df.groupby(["cluster", "cluster_label"])[metrics].mean().reset_index()
    scaled_values = MinMaxScaler().fit_transform(mean_df[metrics])
    angles = radar_angles(len(metrics))

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, polar=True)
    colors = [config.COLORS["primary"], config.COLORS["accent_warm"], config.COLORS["accent_green"], config.COLORS["secondary"], "#90E0EF", "#F9A03F"]
    for index, row in mean_df.iterrows():
        values = np.concatenate([scaled_values[index], [scaled_values[index][0]]])
        ax.plot(angles, values, linewidth=2, label=f"{int(row['cluster'])} - {row['cluster_label']}", color=colors[index % len(colors)])
        ax.fill(angles, values, alpha=0.10, color=colors[index % len(colors)])
    ax.set_thetagrids(angles[:-1] * 180 / np.pi, labels)
    ax.set_title("K-Means 用户群体画像雷达图")
    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.10))
    save_figure(fig, config.CLUSTERING_OUTPUT_DIR / "clustering_radar.png")


def plot_pca_scatter(clustered_df: pd.DataFrame, features: np.ndarray) -> None:
    """绘制 PCA 降维散点图。"""
    if clustered_df.empty:
        return
    fig, ax = create_figure()
    if len(clustered_df) < 2:
        ax.scatter([0], [0], color=config.COLORS["primary"], s=80)
    else:
        pca = PCA(n_components=2, random_state=config.RANDOM_STATE)
        components = pca.fit_transform(features)
        scatter = ax.scatter(
            components[:, 0],
            components[:, 1],
            c=clustered_df["cluster"],
            cmap="viridis",
            s=45,
            alpha=0.8,
        )
        fig.colorbar(scatter, ax=ax, label="聚类编号")
    ax.set_title("用户聚类 PCA 降维散点图")
    ax.set_xlabel("主成分 1")
    ax.set_ylabel("主成分 2")
    save_figure(fig, config.CLUSTERING_OUTPUT_DIR / "clustering_pca_scatter.png")


def plot_cluster_share(clustered_df: pd.DataFrame) -> None:
    """绘制聚类用户数占比。"""
    if clustered_df.empty:
        return
    share_df = clustered_df["cluster_label"].value_counts()
    fig, ax = create_figure()
    ax.pie(share_df.values, labels=share_df.index, autopct="%1.1f%%", startangle=90)
    ax.set_title("聚类群体用户数占比")
    save_figure(fig, config.CLUSTERING_OUTPUT_DIR / "clustering_share.png")


def run_clustering(k: int = config.KMEANS_OPTIMAL_K) -> tuple[pd.DataFrame, dict[str, object]]:
    """执行 K-Means 聚类分析。"""
    ensure_directories()
    logger = get_logger("clustering")
    with log_step(logger, "加载 RFM 数据"):
        rfm = load_or_build_rfm()
    with log_step(logger, "准备聚类特征"):
        feature_df, features = prepare_features(rfm)
        selected_k = resolve_k(len(feature_df), k)
    with log_step(logger, "训练聚类模型"):
        elbow_df = calculate_elbow(features)
        clustered_df = assign_clusters(feature_df, features, selected_k)
        summary = summarize_clusters(clustered_df, elbow_df, selected_k)
    with log_step(logger, "保存聚类结果"):
        save_dataframe(clustered_df, config.CLUSTERING_RESULT_PATH, logger=logger)
        save_json(summary, config.CLUSTERING_SUMMARY_PATH)
    with log_step(logger, "生成聚类可视化图表"):
        plot_elbow(elbow_df)
        plot_radar(clustered_df)
        plot_pca_scatter(clustered_df, features)
        plot_cluster_share(clustered_df)
    return clustered_df, summary


def main() -> None:
    """脚本入口。"""
    clustered_df, summary = run_clustering()
    print("K-Means 聚类分析完成。")
    print(f"聚类用户数：{len(clustered_df):,}")
    print(f"实际 K 值：{summary['selected_k']}")
    print(f"群体摘要：{summary['clusters']}")


if __name__ == "__main__":
    main()
