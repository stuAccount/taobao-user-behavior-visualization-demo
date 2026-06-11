"""原始电商行为数据清洗模块。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from tqdm import tqdm

from analysis import config
from analysis.utils import (
    ensure_directories,
    get_logger,
    log_step,
    save_dataframe,
    save_json,
    validate_raw_data_file,
)


@dataclass
class CleaningStats:
    """记录数据清洗统计信息。"""

    raw_rows: int = 0
    after_chunk_dedup_rows: int = 0
    after_behavior_filter_rows: int = 0
    invalid_behavior_rows: int = 0
    chunk_count: int = 0


def read_raw_chunks(path: Path, chunksize: int = config.CHUNK_SIZE):
    """按块读取原始数据。"""
    return pd.read_csv(
        path,
        names=config.COLUMNS,
        chunksize=chunksize,
        header=None,
    )


def clean_single_chunk(chunk: pd.DataFrame, stats: CleaningStats) -> pd.DataFrame:
    """清洗单个数据块。"""
    stats.raw_rows += len(chunk)

    chunk = chunk.drop_duplicates(subset=["user_id", "item_id", "timestamp"])
    stats.after_chunk_dedup_rows += len(chunk)

    chunk = chunk[chunk["behavior"].isin(config.VALID_BEHAVIORS)].copy()
    stats.after_behavior_filter_rows += len(chunk)
    stats.invalid_behavior_rows = stats.after_chunk_dedup_rows - stats.after_behavior_filter_rows

    datetime_series = (
        pd.to_datetime(chunk["timestamp"], unit="s", utc=True)
        .dt.tz_convert(config.TIMEZONE)
        .dt.tz_localize(None)
    )
    chunk["datetime"] = datetime_series
    chunk["date"] = datetime_series.dt.strftime("%Y-%m-%d")
    chunk["hour"] = datetime_series.dt.hour.astype("int8")
    chunk["weekday"] = datetime_series.dt.weekday.astype("int8")

    for column in ["user_id", "item_id", "category_id"]:
        chunk[column] = pd.to_numeric(chunk[column], errors="coerce").fillna(-1).astype("int32")
    chunk["behavior"] = chunk["behavior"].astype("category")

    return chunk


def consolidate_cleaned_chunks(chunk_paths: list[Path], logger) -> pd.DataFrame:
    """合并分块结果并执行全局去重。"""
    if not chunk_paths:
        return pd.DataFrame(columns=config.COLUMNS + ["datetime", "date", "hour", "weekday"])

    logger.info("开始合并 %s 个临时数据块。", len(chunk_paths))
    frames: list[pd.DataFrame] = []
    for chunk_path in tqdm(chunk_paths, desc="合并清洗块", unit="块"):
        if chunk_path.suffix == ".parquet":
            frames.append(pd.read_parquet(chunk_path))
        else:
            frames.append(pd.read_csv(chunk_path, parse_dates=["datetime"]))

    merged_df = pd.concat(frames, ignore_index=True)
    before_global_dedup = len(merged_df)
    merged_df = merged_df.drop_duplicates(subset=["user_id", "item_id", "timestamp"])
    logger.info(
        "全局去重完成：去重前 %s 行，去重后 %s 行，去重率 %.2f%%。",
        before_global_dedup,
        len(merged_df),
        (before_global_dedup - len(merged_df)) / before_global_dedup * 100 if before_global_dedup else 0,
    )
    return merged_df


def build_summary(df: pd.DataFrame, stats: CleaningStats, output_path: Path) -> dict[str, object]:
    """构建数据清洗摘要。"""
    behavior_counts = df["behavior"].astype(str).value_counts().to_dict() if not df.empty else {}
    summary = {
        "raw_rows": stats.raw_rows,
        "after_chunk_dedup_rows": stats.after_chunk_dedup_rows,
        "after_behavior_filter_rows": stats.after_behavior_filter_rows,
        "final_rows": int(len(df)),
        "invalid_behavior_rows": stats.invalid_behavior_rows,
        "chunk_count": stats.chunk_count,
        "behavior_counts": behavior_counts,
        "date_range": {
            "start": df["datetime"].min().strftime("%Y-%m-%d %H:%M:%S") if not df.empty else None,
            "end": df["datetime"].max().strftime("%Y-%m-%d %H:%M:%S") if not df.empty else None,
        },
        "output_path": str(output_path),
    }
    return summary


def clean_data(raw_data_path: Path = config.RAW_DATA_PATH) -> tuple[Path, dict[str, object]]:
    """执行完整数据清洗流程。"""
    ensure_directories()
    validate_raw_data_file()
    logger = get_logger("data_cleaning")
    temp_dir = config.CLEANED_DATA_DIR / "_tmp_chunks"
    if temp_dir.exists():
        shutil.rmtree(temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)

    stats = CleaningStats()
    chunk_paths: list[Path] = []

    with log_step(logger, "分块读取与清洗原始数据"):
        for index, chunk in enumerate(read_raw_chunks(raw_data_path), start=1):
            stats.chunk_count += 1
            cleaned_chunk = clean_single_chunk(chunk, stats)
            temp_path = temp_dir / f"chunk_{index:04d}.parquet"
            saved_path = save_dataframe(cleaned_chunk, temp_path, logger=logger)
            chunk_paths.append(saved_path)
            logger.info(
                "第 %s 块处理完成：原始 %s 行，清洗后 %s 行。",
                index,
                len(chunk),
                len(cleaned_chunk),
            )

    with log_step(logger, "合并分块并执行全局去重"):
        cleaned_df = consolidate_cleaned_chunks(chunk_paths, logger)

    final_path = config.CLEANED_PARQUET_PATH
    with log_step(logger, "保存清洗结果"):
        saved_output_path = save_dataframe(cleaned_df, final_path, logger=logger)

    summary = build_summary(cleaned_df, stats, saved_output_path)
    save_json(summary, config.CLEANING_SUMMARY_PATH)

    shutil.rmtree(temp_dir, ignore_errors=True)
    logger.info("数据清洗完成，摘要已保存至：%s", config.CLEANING_SUMMARY_PATH)
    return saved_output_path, summary


def main() -> None:
    """脚本入口。"""
    output_path, summary = clean_data()
    print("数据清洗完成。")
    print(f"输出文件：{output_path}")
    print(f"记录数：{summary['final_rows']:,}")
    print(f"时间范围：{summary['date_range']['start']} ~ {summary['date_range']['end']}")
    print(f"行为分布：{summary['behavior_counts']}")


if __name__ == "__main__":
    main()
