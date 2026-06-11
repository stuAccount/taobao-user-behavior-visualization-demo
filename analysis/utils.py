"""分析模块通用工具函数。"""

from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import pandas as pd

from analysis import config


def ensure_directories() -> None:
    """创建项目运行所需目录。"""
    for directory in config.OUTPUT_DIRECTORIES:
        directory.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    """获取统一格式的日志记录器。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger(name)


@contextmanager
def log_step(logger: logging.Logger, step_name: str) -> Iterator[None]:
    """记录步骤耗时。"""
    start = time.perf_counter()
    logger.info("开始：%s", step_name)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.info("完成：%s，用时 %.2f 秒", step_name, elapsed)


def save_json(data: dict[str, Any], path: Path) -> None:
    """保存 JSON 文件。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2, default=str)


def load_json(path: Path, default: Any = None) -> Any:
    """读取 JSON 文件。"""
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_dataframe(df: pd.DataFrame, path: Path, logger: logging.Logger | None = None) -> Path:
    """优先保存为 Parquet，失败时回退为 CSV。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        df.to_parquet(path, index=False)
        if logger:
            logger.info("已保存文件：%s", path)
        return path
    except Exception as exc:  # pragma: no cover - 回退逻辑依赖环境
        fallback_path = path.with_suffix(".csv")
        df.to_csv(fallback_path, index=False)
        if logger:
            logger.warning("保存 Parquet 失败，已回退为 CSV：%s，原因：%s", fallback_path, exc)
        return fallback_path


def read_table(path: Path, **kwargs: Any) -> pd.DataFrame:
    """根据扩展名读取表格数据。"""
    if path.suffix == ".parquet":
        return pd.read_parquet(path, **kwargs)
    if path.suffix == ".csv":
        return pd.read_csv(path, **kwargs)
    raise ValueError(f"不支持的文件类型：{path}")


def find_first_existing_path(candidates: list[Path]) -> Path | None:
    """返回第一个存在的路径。"""
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_cleaned_data_path() -> Path:
    """获取清洗后数据文件路径。"""
    cleaned_path = find_first_existing_path(
        [config.CLEANED_PARQUET_PATH, config.CLEANED_CSV_PATH]
    )
    if cleaned_path is None:
        raise FileNotFoundError(
            "未找到清洗后数据，请先运行 `python -m analysis.data_cleaning`。"
        )
    return cleaned_path


def load_cleaned_data(columns: list[str] | None = None) -> pd.DataFrame:
    """加载清洗后数据。"""
    cleaned_path = get_cleaned_data_path()
    if cleaned_path.suffix == ".parquet":
        return pd.read_parquet(cleaned_path, columns=columns)
    return pd.read_csv(cleaned_path, usecols=columns, parse_dates=["datetime"])


def validate_raw_data_file() -> None:
    """检查原始数据文件是否存在。"""
    if not config.RAW_DATA_PATH.exists():
        raise FileNotFoundError(
            "未找到原始数据文件 data/UserBehavior.csv。\n"
            "请先执行 `bash scripts/download_data.sh` 下载，"
            "或从 Kaggle/天池下载后放入 data/ 目录。"
        )


def print_section(title: str) -> None:
    """打印分节标题。"""
    line = "=" * 18
    print(f"{line} {title} {line}")
