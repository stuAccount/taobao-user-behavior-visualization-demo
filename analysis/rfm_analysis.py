"""RFM 用户价值分析模块。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from analysis import config
from analysis.utils import ensure_directories, get_logger, load_cleaned_data, log_step, save_dataframe, save_json
from analysis.visualization import create_figure, save_figure

SEGMENT_LABELS = {
    (1, 1, 1): "一般挽留用户",
    (1, 1, 2): "一般保持用户",
    (1, 2, 1): "一般发展用户",
    (1, 2, 2): "一般价值用户",
    (2, 1, 1): "重要挽留用户",
    (2, 1, 2): "重要保持用户",
    (2, 2, 1): "重要发展用户",
    (2, 2, 2): "重要价值用户",
}


def build_rfm_table(df: pd.DataFrame, monetary_mode: str = config.RFM_MONETARY_MODE) -> pd.DataFrame:
    """基于购买行为构建 RFM 指标表。"""
    buy_df = df[df["behavior"].astype(str) == "buy"].copy()
    if buy_df.empty:
        return pd.DataFrame(
            columns=[
                "user_id",
                "recency",
                "frequency",
                "monetary",
                "last_buy_time",
                "r_score",
                "f_score",
                "m_score",
                "segment",
            ]
        )

    buy_df["datetime"] = pd.to_datetime(buy_df["datetime"])
    analysis_end = pd.Timestamp(config.ANALYSIS_END_DATE)
    grouped = buy_df.groupby("user_id").agg(
        last_buy_time=("datetime", "max"),
        frequency=("item_id", "count"),
        category_count=("category_id", "nunique"),
    )
    grouped["recency"] = (analysis_end - grouped["last_buy_time"]).dt.days.clip(lower=0)
    grouped["monetary"] = (
        grouped["category_count"] if monetary_mode == "category_count" else grouped["frequency"]
    )
    rfm = grouped.reset_index()
    return score_rfm_table(rfm)


def _binary_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    """根据中位数做高低二分打分。"""
    if series.empty:
        return pd.Series(dtype="int8")
    median_value = series.median()
    if higher_is_better:
        score = np.where(series >= median_value, 2, 1)
    else:
        score = np.where(series <= median_value, 2, 1)
    return pd.Series(score, index=series.index, dtype="int8")


def _three_level_score(series: pd.Series, higher_is_better: bool) -> pd.Series:
    """根据分位数做三档打分，分位点重复时回退为二分。"""
    if series.nunique(dropna=True) < config.RFM_SCORE_BINS:
        return _binary_score(series, higher_is_better)

    labels = [1, 2, 3] if higher_is_better else [3, 2, 1]
    try:
        ranked = series.rank(method="first")
        return pd.qcut(ranked, q=config.RFM_SCORE_BINS, labels=labels).astype("int8")
    except ValueError:
        return _binary_score(series, higher_is_better)


def score_rfm_table(rfm: pd.DataFrame) -> pd.DataFrame:
    """计算 RFM 分数和用户分层。"""
    if rfm.empty:
        return rfm

    rfm = rfm.copy()
    rfm["r_score"] = _three_level_score(rfm["recency"], higher_is_better=False)
    rfm["f_score"] = _three_level_score(rfm["frequency"], higher_is_better=True)
    rfm["m_score"] = _three_level_score(rfm["monetary"], higher_is_better=True)

    rfm["r_level"] = _binary_score(rfm["recency"], higher_is_better=False)
    rfm["f_level"] = _binary_score(rfm["frequency"], higher_is_better=True)
    rfm["m_level"] = _binary_score(rfm["monetary"], higher_is_better=True)
    rfm["segment"] = [
        SEGMENT_LABELS[(int(r), int(f), int(m))]
        for r, f, m in zip(rfm["r_level"], rfm["f_level"], rfm["m_level"])
    ]
    return rfm


def summarize_rfm(rfm: pd.DataFrame) -> dict[str, object]:
    """生成 RFM 汇总信息。"""
    if rfm.empty:
        return {
            "total_buy_users": 0,
            "segment_counts": {},
            "segment_ratio": {},
            "rfm_mean_by_segment": {},
        }

    segment_counts = rfm["segment"].value_counts().to_dict()
    segment_ratio = (rfm["segment"].value_counts(normalize=True) * 100).round(2).to_dict()
    rfm_mean = (
        rfm.groupby("segment")[["recency", "frequency", "monetary"]]
        .mean()
        .round(2)
        .to_dict(orient="index")
    )
    return {
        "total_buy_users": int(rfm["user_id"].nunique()),
        "segment_counts": {key: int(value) for key, value in segment_counts.items()},
        "segment_ratio": segment_ratio,
        "rfm_mean_by_segment": rfm_mean,
    }


def plot_rfm_distributions(rfm: pd.DataFrame) -> None:
    """绘制 RFM 分布直方图。"""
    if rfm.empty:
        return
    from analysis.visualization import configure_matplotlib

    configure_matplotlib()
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    metrics = [("recency", "最近购买间隔天数"), ("frequency", "购买次数"), ("monetary", "购买类目数")]
    for ax, (column, title) in zip(axes, metrics):
        ax.hist(rfm[column], bins=min(20, max(3, rfm[column].nunique())), color=config.COLORS["primary"], edgecolor="white")
        ax.set_title(title)
        ax.set_xlabel(title)
        ax.set_ylabel("用户数")
    save_figure(fig, config.RFM_OUTPUT_DIR / "rfm_distribution.png")


def plot_segment_share(rfm: pd.DataFrame) -> None:
    """绘制用户分层占比环形图。"""
    if rfm.empty:
        return
    segment_counts = rfm["segment"].value_counts()
    fig, ax = create_figure()
    colors = [
        config.COLORS["primary"],
        config.COLORS["secondary"],
        config.COLORS["accent_warm"],
        config.COLORS["accent_green"],
        "#90E0EF",
        "#48CAE4",
        "#F9A03F",
        "#80ED99",
    ]
    wedges, texts, autotexts = ax.pie(
        segment_counts.values,
        labels=segment_counts.index,
        autopct="%1.1f%%",
        startangle=90,
        colors=colors[: len(segment_counts)],
        pctdistance=0.82,
    )
    centre_circle = plt.Circle((0, 0), 0.60, fc="white")
    ax.add_artist(centre_circle)
    _ = (wedges, texts, autotexts)
    ax.set_title("RFM 用户分层占比")
    save_figure(fig, config.RFM_OUTPUT_DIR / "rfm_segment_share.png")


def plot_segment_means(rfm: pd.DataFrame) -> None:
    """绘制各用户分层 RFM 均值对比图。"""
    if rfm.empty:
        return
    mean_df = rfm.groupby("segment")[["recency", "frequency", "monetary"]].mean().sort_values("frequency", ascending=False)
    fig, ax = create_figure((14, 8))
    mean_df.plot(kind="bar", ax=ax, color=[config.COLORS["accent_warm"], config.COLORS["primary"], config.COLORS["accent_green"]])
    ax.set_title("各用户分层 RFM 均值对比")
    ax.set_xlabel("用户分层")
    ax.set_ylabel("指标均值")
    ax.tick_params(axis="x", rotation=35)
    ax.legend(["R 最近购买间隔", "F 购买次数", "M 购买类目数"])
    save_figure(fig, config.RFM_OUTPUT_DIR / "rfm_segment_means.png")


def run_rfm_analysis() -> tuple[pd.DataFrame, dict[str, object]]:
    """执行 RFM 分析。"""
    ensure_directories()
    logger = get_logger("rfm_analysis")
    with log_step(logger, "加载清洗后数据"):
        df = load_cleaned_data(columns=["user_id", "item_id", "category_id", "behavior", "datetime"])
    with log_step(logger, "构建 RFM 指标"):
        rfm = build_rfm_table(df)
    with log_step(logger, "保存 RFM 结果"):
        save_dataframe(rfm, config.RFM_RESULT_PATH, logger=logger)
        summary = summarize_rfm(rfm)
        save_json(summary, config.RFM_SUMMARY_PATH)
    with log_step(logger, "生成 RFM 可视化图表"):
        plot_rfm_distributions(rfm)
        plot_segment_share(rfm)
        plot_segment_means(rfm)
    return rfm, summary


def main() -> None:
    """脚本入口。"""
    rfm, summary = run_rfm_analysis()
    print("RFM 分析完成。")
    print(f"购买用户数：{summary['total_buy_users']:,}")
    print(f"用户分层：{summary['segment_counts']}")
    print(f"结果行数：{len(rfm):,}")


if __name__ == "__main__":
    main()
