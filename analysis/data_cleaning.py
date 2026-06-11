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
    after_date_filter_rows: int = 0
    invalid_behavior_rows: int = 0
    out_of_range_rows: int = 0
    global_duplicate_rows: int = 0
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

    start_date = pd.Timestamp(config.DATE_RANGE[0])
    end_date = pd.Timestamp(config.DATE_RANGE[1]) + pd.Timedelta(days=1)
    before_date_filter = len(chunk)
    chunk = chunk[(chunk["datetime"] >= start_date) & (chunk["datetime"] < end_date)].copy()
    stats.after_date_filter_rows += len(chunk)
    stats.out_of_range_rows += before_date_filter - len(chunk)

    for column in ["user_id", "item_id", "category_id"]:
        chunk[column] = pd.to_numeric(chunk[column], errors="coerce").fillna(-1).astype("int32")
    chunk["behavior"] = chunk["behavior"].astype("category")

    return chunk


def build_summary(
    stats: CleaningStats,
    output_path: Path,
    final_rows: int,
    behavior_counts: dict[str, int],
    user_ids: set[int],
    item_ids: set[int],
    category_ids: set[int],
    min_datetime: pd.Timestamp | None,
    max_datetime: pd.Timestamp | None,
) -> dict[str, object]:
    """构建数据清洗摘要。"""
    summary = {
        "raw_rows": stats.raw_rows,
        "after_chunk_dedup_rows": stats.after_chunk_dedup_rows,
        "after_behavior_filter_rows": stats.after_behavior_filter_rows,
        "after_date_filter_rows": stats.after_date_filter_rows,
        "final_rows": int(final_rows),
        "user_count": len(user_ids),
        "item_count": len(item_ids),
        "category_count": len(category_ids),
        "invalid_behavior_rows": stats.invalid_behavior_rows,
        "out_of_range_rows": stats.out_of_range_rows,
        "global_duplicate_rows": stats.global_duplicate_rows,
        "chunk_count": stats.chunk_count,
        "behavior_counts": behavior_counts,
        "date_range": {
            "start": min_datetime.strftime("%Y-%m-%d %H:%M:%S") if min_datetime is not None else None,
            "end": max_datetime.strftime("%Y-%m-%d %H:%M:%S") if max_datetime is not None else None,
        },
        "output_path": str(output_path),
    }
    return summary


def clean_data(raw_data_path: Path = config.RAW_DATA_PATH) -> tuple[Path, dict[str, object]]:
    """执行完整数据清洗流程。"""
    ensure_directories()
    validate_raw_data_file()
    logger = get_logger("data_cleaning")
    if config.CLEANED_CHUNK_DIR.exists():
        shutil.rmtree(config.CLEANED_CHUNK_DIR)
    config.CLEANED_CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in [config.CLEANED_PARQUET_PATH, config.CLEANED_CSV_PATH]:
        old_file.unlink(missing_ok=True)

    stats = CleaningStats()
    chunk_paths: list[Path] = []
    seen_hashes: set[int] = set()
    behavior_counts: dict[str, int] = {}
    user_ids: set[int] = set()
    item_ids: set[int] = set()
    category_ids: set[int] = set()
    final_rows = 0
    min_datetime: pd.Timestamp | None = None
    max_datetime: pd.Timestamp | None = None

    with log_step(logger, "分块读取与清洗原始数据"):
        for index, chunk in enumerate(read_raw_chunks(raw_data_path), start=1):
            stats.chunk_count += 1
            cleaned_chunk = clean_single_chunk(chunk, stats)
            if not cleaned_chunk.empty:
                row_hashes = pd.util.hash_pandas_object(
                    cleaned_chunk[["user_id", "item_id", "timestamp"]],
                    index=False,
                ).astype("uint64")
                unique_mask = ~row_hashes.isin(seen_hashes)
                stats.global_duplicate_rows += int((~unique_mask).sum())
                seen_hashes.update(row_hashes[unique_mask].tolist())
                cleaned_chunk = cleaned_chunk.loc[unique_mask].copy()

            if cleaned_chunk.empty:
                logger.info("第 %s 块清洗后无有效记录。", index)
                continue

            temp_path = config.CLEANED_CHUNK_DIR / f"part_{index:04d}.parquet"
            saved_path = save_dataframe(cleaned_chunk, temp_path, logger=logger)
            chunk_paths.append(saved_path)
            final_rows += len(cleaned_chunk)
            for behavior, count in cleaned_chunk["behavior"].astype(str).value_counts().items():
                behavior_counts[behavior] = behavior_counts.get(behavior, 0) + int(count)
            user_ids.update(cleaned_chunk["user_id"].astype(int).unique().tolist())
            item_ids.update(cleaned_chunk["item_id"].astype(int).unique().tolist())
            category_ids.update(cleaned_chunk["category_id"].astype(int).unique().tolist())
            chunk_min = cleaned_chunk["datetime"].min()
            chunk_max = cleaned_chunk["datetime"].max()
            min_datetime = chunk_min if min_datetime is None else min(min_datetime, chunk_min)
            max_datetime = chunk_max if max_datetime is None else max(max_datetime, chunk_max)
            logger.info(
                "第 %s 块处理完成：原始 %s 行，清洗后 %s 行。",
                index,
                len(chunk),
                len(cleaned_chunk),
            )

    saved_output_path: Path = config.CLEANED_CHUNK_DIR
    if final_rows <= config.CLEANED_COMBINE_ROW_LIMIT and chunk_paths:
        with log_step(logger, "小数据集合并为单文件"):
            frames = [pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, parse_dates=["datetime"]) for path in tqdm(chunk_paths, desc="合并小样本", unit="块")]
            combined_df = pd.concat(frames, ignore_index=True)
            saved_output_path = save_dataframe(combined_df, config.CLEANED_PARQUET_PATH, logger=logger)

    summary = build_summary(
        stats,
        saved_output_path,
        final_rows,
        behavior_counts,
        user_ids,
        item_ids,
        category_ids,
        min_datetime,
        max_datetime,
    )
    save_json(summary, config.CLEANING_SUMMARY_PATH)

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
