"""原始电商行为数据清洗模块。"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
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


def _try_import_polars():
    """延迟导入 Polars，便于缺失依赖时回退到 pandas。"""
    if (
        not os.getenv("POLARS_MAX_THREADS")
        and config.POLARS_MAX_THREADS != "auto"
    ):
        os.environ["POLARS_MAX_THREADS"] = str(config.POLARS_MAX_THREADS)
    try:
        import polars as pl
    except ImportError:
        return None
    return pl


def _prepare_output_paths() -> None:
    """清理旧清洗产物并创建输出目录。"""
    if config.CLEANED_CHUNK_DIR.exists():
        shutil.rmtree(config.CLEANED_CHUNK_DIR)
    config.CLEANED_CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    for old_file in [config.CLEANED_PARQUET_PATH, config.CLEANED_CSV_PATH]:
        old_file.unlink(missing_ok=True)


def _count_csv_rows_fast(path: Path) -> int:
    """用二进制方式快速统计 CSV 行数。"""
    row_count = 0
    last_block = b""
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024 * 16), b""):
            row_count += block.count(b"\n")
            last_block = block
    if last_block and not last_block.endswith(b"\n"):
        row_count += 1
    return row_count


def _build_polars_lazy_frame(raw_data_path: Path):
    """构建 Polars 懒执行清洗计划。"""
    pl = _try_import_polars()
    if pl is None:  # pragma: no cover - 调用方会先判断依赖
        raise ImportError("未安装 polars")

    start_datetime = datetime.fromisoformat(config.DATE_RANGE[0])
    end_datetime = datetime.fromisoformat(config.DATE_RANGE[1]) + timedelta(days=1)
    schema_overrides = {
        "user_id": pl.Int64,
        "item_id": pl.Int64,
        "category_id": pl.Int64,
        "behavior": pl.String,
        "timestamp": pl.Int64,
    }

    raw_lf = pl.scan_csv(
        raw_data_path,
        has_header=False,
        new_columns=config.COLUMNS,
        schema_overrides=schema_overrides,
        infer_schema=False,
        low_memory=False,
    )

    datetime_expr = pl.from_epoch("timestamp", time_unit="s").dt.offset_by("8h")
    return (
        raw_lf.filter(pl.col("behavior").is_in(config.VALID_BEHAVIORS))
        .with_columns(datetime_expr.alias("datetime"))
        .filter(
            (pl.col("datetime") >= pl.lit(start_datetime))
            & (pl.col("datetime") < pl.lit(end_datetime))
        )
        .unique(
            subset=["user_id", "item_id", "timestamp"],
            keep="first",
            maintain_order=False,
        )
        .with_columns(
            [
                pl.col("user_id").cast(pl.Int32),
                pl.col("item_id").cast(pl.Int32),
                pl.col("category_id").cast(pl.Int32),
                pl.col("behavior").cast(pl.Categorical),
                pl.col("datetime").dt.strftime("%Y-%m-%d").alias("date"),
                pl.col("datetime").dt.hour().cast(pl.Int8).alias("hour"),
                (pl.col("datetime").dt.weekday() - 1).cast(pl.Int8).alias("weekday"),
            ]
        )
        .select(
            [
                "user_id",
                "item_id",
                "category_id",
                "behavior",
                "timestamp",
                "datetime",
                "date",
                "hour",
                "weekday",
            ]
        )
    )


def _collect_polars_summary(output_path: Path, raw_data_path: Path, raw_rows: int) -> dict[str, object]:
    """从清洗后的 Parquet 结果中收集轻量摘要。"""
    pl = _try_import_polars()
    if pl is None:  # pragma: no cover - 调用方会先判断依赖
        raise ImportError("未安装 polars")

    cleaned_lf = pl.scan_parquet(output_path)
    overview = cleaned_lf.select(
        [
            pl.len().alias("final_rows"),
            pl.col("user_id").n_unique().alias("user_count"),
            pl.col("item_id").n_unique().alias("item_count"),
            pl.col("category_id").n_unique().alias("category_count"),
            pl.col("datetime").min().alias("min_datetime"),
            pl.col("datetime").max().alias("max_datetime"),
        ]
    ).collect()
    overview_row = overview.to_dicts()[0]
    behavior_rows = (
        cleaned_lf.group_by("behavior")
        .len()
        .collect()
        .sort("behavior")
        .to_dicts()
    )
    behavior_counts = {
        str(row["behavior"]): int(row["len"])
        for row in behavior_rows
    }

    min_datetime = overview_row["min_datetime"]
    max_datetime = overview_row["max_datetime"]
    final_rows = int(overview_row["final_rows"])
    summary = {
        "engine": "polars",
        "stats_mode": config.CLEANING_STATS_MODE,
        "polars_threads": _get_polars_thread_count(),
        "raw_rows": int(raw_rows),
        "after_chunk_dedup_rows": None,
        "after_behavior_filter_rows": None,
        "after_date_filter_rows": None,
        "final_rows": final_rows,
        "user_count": int(overview_row["user_count"]),
        "item_count": int(overview_row["item_count"]),
        "category_count": int(overview_row["category_count"]),
        "invalid_behavior_rows": None,
        "out_of_range_rows": None,
        "global_duplicate_rows": None,
        "total_removed_rows": max(int(raw_rows) - final_rows, 0),
        "chunk_count": None,
        "behavior_counts": behavior_counts,
        "date_range": {
            "start": min_datetime.strftime("%Y-%m-%d %H:%M:%S") if min_datetime else None,
            "end": max_datetime.strftime("%Y-%m-%d %H:%M:%S") if max_datetime else None,
        },
        "output_path": str(output_path),
        "note": "Polars 高速模式默认只保证最终摘要；如需过滤阶段精确计数，可设置 CLEANING_STATS_MODE=full。",
    }

    if config.CLEANING_STATS_MODE == "full":
        summary.update(_collect_polars_full_stats(output_path, raw_data_path, raw_rows))
    return summary


def _collect_polars_full_stats(output_path: Path, raw_data_path: Path, raw_rows: int) -> dict[str, object]:
    """收集完整统计字段；会额外扫描一次原始 CSV，速度优先时不建议开启。"""
    pl = _try_import_polars()
    if pl is None:  # pragma: no cover - 调用方会先判断依赖
        raise ImportError("未安装 polars")

    # 完整统计需要按清洗条件额外聚合一次，主要用于课程报告审计而非最快路径。
    raw_lf = pl.scan_csv(
        raw_data_path,
        has_header=False,
        new_columns=config.COLUMNS,
        schema_overrides={
            "user_id": pl.Int64,
            "item_id": pl.Int64,
            "category_id": pl.Int64,
            "behavior": pl.String,
            "timestamp": pl.Int64,
        },
        infer_schema=False,
        low_memory=False,
    )
    start_datetime = datetime.fromisoformat(config.DATE_RANGE[0])
    end_datetime = datetime.fromisoformat(config.DATE_RANGE[1]) + timedelta(days=1)
    with_datetime = raw_lf.filter(pl.col("behavior").is_in(config.VALID_BEHAVIORS)).with_columns(
        pl.from_epoch("timestamp", time_unit="s").dt.offset_by("8h").alias("datetime")
    )
    full_stats = with_datetime.select(
        [
            pl.len().alias("after_behavior_filter_rows"),
            (
                (pl.col("datetime") < pl.lit(start_datetime))
                | (pl.col("datetime") >= pl.lit(end_datetime))
            ).sum().alias("out_of_range_rows"),
        ]
    ).collect().to_dicts()[0]
    final_rows = pl.scan_parquet(output_path).select(pl.len()).collect().item()
    after_behavior = int(full_stats["after_behavior_filter_rows"])
    out_of_range = int(full_stats["out_of_range_rows"])
    after_date = after_behavior - out_of_range
    return {
        "after_behavior_filter_rows": after_behavior,
        "after_date_filter_rows": after_date,
        "invalid_behavior_rows": int(raw_rows) - after_behavior,
        "out_of_range_rows": out_of_range,
        "global_duplicate_rows": max(after_date - int(final_rows), 0),
        "total_removed_rows": max(int(raw_rows) - int(final_rows), 0),
    }


def _get_polars_thread_count() -> int | str:
    """读取 Polars 线程池大小。"""
    pl = _try_import_polars()
    if pl is None:
        return "unavailable"
    if hasattr(pl, "thread_pool_size"):
        return int(pl.thread_pool_size())
    return int(pl.threadpool_size())


def _clean_data_with_polars(raw_data_path: Path, logger) -> tuple[Path, dict[str, object]]:
    """使用 Polars 多线程执行高速清洗。"""
    pl = _try_import_polars()
    if pl is None:
        raise ImportError("未安装 polars")

    logger.info(
        "启用 Polars 多线程清洗：线程池=%s，POLARS_MAX_THREADS=%s。",
        _get_polars_thread_count(),
        os.getenv("POLARS_MAX_THREADS", "未设置"),
    )
    cleaned_lf = _build_polars_lazy_frame(raw_data_path)
    with log_step(logger, "Polars 并行清洗并写出 Parquet"):
        cleaned_lf.sink_parquet(
            config.CLEANED_PARQUET_PATH,
            compression="zstd",
            statistics=True,
            row_group_size=config.PARQUET_ROW_GROUP_SIZE,
            mkdir=True,
            maintain_order=False,
        )

    with log_step(logger, "生成清洗摘要"):
        raw_rows = _count_csv_rows_fast(raw_data_path)
        summary = _collect_polars_summary(config.CLEANED_PARQUET_PATH, raw_data_path, raw_rows)
        summary["polars_version"] = pl.__version__
    save_json(summary, config.CLEANING_SUMMARY_PATH)
    return config.CLEANED_PARQUET_PATH, summary


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
        "engine": "pandas",
        "stats_mode": "full",
        "polars_threads": None,
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
    if raw_data_path == config.RAW_DATA_PATH:
        validate_raw_data_file()
    elif not raw_data_path.exists():
        raise FileNotFoundError(f"未找到原始数据文件：{raw_data_path}")
    logger = get_logger("data_cleaning")
    _prepare_output_paths()

    if config.CLEANING_ENGINE == "polars":
        try:
            output_path, summary = _clean_data_with_polars(raw_data_path, logger)
            save_json(summary, config.CLEANING_SUMMARY_PATH)
            logger.info("数据清洗完成，摘要已保存至：%s", config.CLEANING_SUMMARY_PATH)
            return output_path, summary
        except ImportError as exc:
            logger.warning("Polars 不可用，回退到 pandas 分块清洗：%s", exc)
        except Exception:
            logger.exception("Polars 清洗失败，停止执行以避免静默生成错误结果。")
            raise
    elif config.CLEANING_ENGINE != "pandas":
        raise ValueError("CLEANING_ENGINE 仅支持 polars 或 pandas。")

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
