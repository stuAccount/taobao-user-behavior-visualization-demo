"""行为漏斗分析模块。"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from analysis import config
from analysis.utils import ensure_directories, get_logger, load_cleaned_data, log_step, save_dataframe, save_json
from analysis.visualization import create_figure, save_figure

FUNNEL_STEPS = ["pv", "fav", "cart", "buy"]
FUNNEL_LABELS = {
    "pv": "浏览",
    "fav": "收藏",
    "cart": "加购",
    "buy": "购买",
}


def build_funnel_summary(df: pd.DataFrame) -> pd.DataFrame:
    """计算行为漏斗核心指标。"""
    rows = []
    first_times = (
        df.groupby(["user_id", "behavior"])["timestamp"]
        .min()
        .unstack()
        .reindex(columns=FUNNEL_STEPS)
    )
    previous_times: pd.Series | None = None
    previous_uv: int | None = None
    for behavior in FUNNEL_STEPS:
        behavior_df = df[df["behavior"].astype(str) == behavior]
        behavior_times = first_times[behavior].dropna()
        if previous_times is None:
            funnel_times = behavior_times
        else:
            aligned = behavior_times.reindex(previous_times.index).dropna()
            previous_aligned = previous_times.reindex(aligned.index)
            funnel_times = aligned[aligned >= previous_aligned]
        uv = int(len(funnel_times))
        independent_uv = int(behavior_df["user_id"].nunique())
        actions = int(len(behavior_df))
        conversion_rate = uv / previous_uv if previous_uv else 1.0
        loss_rate = 1 - conversion_rate if previous_uv else 0.0
        rows.append(
            {
                "behavior": behavior,
                "label": FUNNEL_LABELS[behavior],
                "uv": uv,
                "independent_uv": independent_uv,
                "actions": actions,
                "conversion_rate": round(conversion_rate, 4),
                "loss_rate": round(loss_rate, 4),
            }
        )
        previous_times = funnel_times
        previous_uv = uv
    return pd.DataFrame(rows)


def build_daily_conversion(df: pd.DataFrame) -> pd.DataFrame:
    """计算每日行为 UV 与购买转化率。"""
    if df.empty:
        return pd.DataFrame(columns=["date", "pv_uv", "fav_uv", "cart_uv", "buy_uv", "buy_conversion_rate"])

    pivot = (
        df.groupby(["date", "behavior"])["user_id"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=FUNNEL_STEPS, fill_value=0)
        .reset_index()
    )
    pivot = pivot.rename(columns={behavior: f"{behavior}_uv" for behavior in FUNNEL_STEPS})
    pivot["buy_conversion_rate"] = (
        pivot["buy_uv"].div(pivot["pv_uv"].replace(0, pd.NA)).fillna(0).round(4)
    )
    return pivot


def build_hourly_conversion(df: pd.DataFrame) -> pd.DataFrame:
    """计算小时级行为 UV 与购买转化率。"""
    if df.empty:
        return pd.DataFrame(columns=["hour", "pv_uv", "fav_uv", "cart_uv", "buy_uv", "buy_conversion_rate"])

    pivot = (
        df.groupby(["hour", "behavior"])["user_id"]
        .nunique()
        .unstack(fill_value=0)
        .reindex(columns=FUNNEL_STEPS, fill_value=0)
        .reset_index()
    )
    pivot = pivot.rename(columns={behavior: f"{behavior}_uv" for behavior in FUNNEL_STEPS})
    pivot["buy_conversion_rate"] = (
        pivot["buy_uv"].div(pivot["pv_uv"].replace(0, pd.NA)).fillna(0).round(4)
    )
    return pivot


def plot_funnel_bar(funnel_df: pd.DataFrame) -> None:
    """绘制经典水平漏斗图。"""
    if funnel_df.empty:
        return
    fig, ax = create_figure((12, 7))
    plot_df = funnel_df.iloc[::-1]
    colors = [config.BEHAVIOR_COLORS[behavior] for behavior in plot_df["behavior"]]
    bars = ax.barh(plot_df["label"], plot_df["uv"], color=colors)
    ax.set_title("用户行为漏斗 UV")
    ax.set_xlabel("独立用户数")
    ax.set_ylabel("行为阶段")
    for bar, uv, rate in zip(bars, plot_df["uv"], plot_df["conversion_rate"]):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" {uv:,}人 / 转化率 {rate:.1%}",
            va="center",
            color=config.COLORS["text_dark"],
        )
    save_figure(fig, config.FUNNEL_OUTPUT_DIR / "funnel_bar.png")


def plot_daily_trend(daily_df: pd.DataFrame) -> None:
    """绘制日维度转化率趋势图。"""
    if daily_df.empty:
        return
    fig, ax = create_figure((14, 7))
    daily_df = daily_df.sort_values("date")
    ax.plot(daily_df["date"], daily_df["buy_conversion_rate"], marker="o", color=config.COLORS["accent_green"])
    ax.set_title("日维度购买转化率趋势")
    ax.set_xlabel("日期")
    ax.set_ylabel("购买转化率")
    ax.tick_params(axis="x", rotation=35)
    ax.yaxis.set_major_formatter(lambda value, _: f"{value:.1%}")
    save_figure(fig, config.FUNNEL_OUTPUT_DIR / "funnel_daily_conversion.png")


def save_sankey_chart(funnel_df: pd.DataFrame) -> None:
    """保存 Plotly 桑基图 HTML。"""
    if funnel_df.empty:
        return
    labels = funnel_df["label"].tolist()
    values = []
    for index in range(len(funnel_df) - 1):
        values.append(int(min(funnel_df.iloc[index]["uv"], funnel_df.iloc[index + 1]["uv"])))
    fig = go.Figure(
        data=[
            go.Sankey(
                node={"label": labels, "color": [config.BEHAVIOR_COLORS[b] for b in FUNNEL_STEPS]},
                link={
                    "source": list(range(len(values))),
                    "target": list(range(1, len(values) + 1)),
                    "value": values,
                    "color": "rgba(0,180,216,0.28)",
                },
            )
        ]
    )
    fig.update_layout(title_text="用户行为转化桑基图", font={"size": 14})
    output_path = config.FUNNEL_OUTPUT_DIR / "funnel_sankey.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(output_path)


def build_summary_payload(
    funnel_df: pd.DataFrame,
    daily_df: pd.DataFrame,
    hourly_df: pd.DataFrame,
) -> dict[str, object]:
    """构建漏斗分析汇总 JSON。"""
    overall_rate = 0.0
    if not funnel_df.empty:
        pv_uv = int(funnel_df.loc[funnel_df["behavior"] == "pv", "uv"].iloc[0])
        buy_uv = int(funnel_df.loc[funnel_df["behavior"] == "buy", "uv"].iloc[0])
        overall_rate = buy_uv / pv_uv if pv_uv else 0.0
    return {
        "funnel": funnel_df.to_dict(orient="records"),
        "daily_rows": int(len(daily_df)),
        "hourly_rows": int(len(hourly_df)),
        "overall_buy_conversion_rate": float(overall_rate),
    }


def run_funnel_analysis() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """执行行为漏斗分析。"""
    ensure_directories()
    logger = get_logger("funnel_analysis")
    with log_step(logger, "加载清洗后数据"):
        df = load_cleaned_data(columns=["user_id", "behavior", "timestamp", "date", "hour"])
    with log_step(logger, "计算漏斗指标"):
        funnel_df = build_funnel_summary(df)
        daily_df = build_daily_conversion(df)
        hourly_df = build_hourly_conversion(df)
    with log_step(logger, "保存漏斗结果"):
        save_dataframe(daily_df, config.FUNNEL_DAILY_PATH, logger=logger)
        hourly_path = config.SUMMARY_DIR / "funnel_hourly.parquet"
        save_dataframe(hourly_df, hourly_path, logger=logger)
        summary = build_summary_payload(funnel_df, daily_df, hourly_df)
        save_json(summary, config.FUNNEL_SUMMARY_PATH)
    with log_step(logger, "生成漏斗可视化图表"):
        plot_funnel_bar(funnel_df)
        plot_daily_trend(daily_df)
        save_sankey_chart(funnel_df)
    return funnel_df, daily_df, summary


def main() -> None:
    """脚本入口。"""
    funnel_df, _, summary = run_funnel_analysis()
    print("漏斗分析完成。")
    print(funnel_df.to_string(index=False))
    print(f"整体购买转化率：{summary['overall_buy_conversion_rate']:.2%}")


if __name__ == "__main__":
    main()
