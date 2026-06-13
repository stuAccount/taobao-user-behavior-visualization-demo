"""项目全局配置。"""

from __future__ import annotations

import os
import platform
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# 路径
RAW_DATA_PATH = BASE_DIR / "data" / "UserBehavior.csv"
CLEANED_DATA_DIR = BASE_DIR / "data" / "cleaned"
OUTPUT_DIR = BASE_DIR / "output"
SUMMARY_DIR = OUTPUT_DIR / "summary"

RFM_OUTPUT_DIR = OUTPUT_DIR / "rfm"
FUNNEL_OUTPUT_DIR = OUTPUT_DIR / "funnel"
CLUSTERING_OUTPUT_DIR = OUTPUT_DIR / "clustering"
ASSOCIATION_OUTPUT_DIR = OUTPUT_DIR / "association"

CLEANED_DATA_FILE_STEM = "user_behavior_cleaned"
CLEANED_CHUNK_DIR = CLEANED_DATA_DIR / "chunks"
CLEANED_PARQUET_PATH = CLEANED_DATA_DIR / f"{CLEANED_DATA_FILE_STEM}.parquet"
CLEANED_CSV_PATH = CLEANED_DATA_DIR / f"{CLEANED_DATA_FILE_STEM}.csv"
CLEANING_SUMMARY_PATH = CLEANED_DATA_DIR / "cleaning_summary.json"
CLEANED_COMBINE_ROW_LIMIT = 2_000_000

RFM_RESULT_PATH = SUMMARY_DIR / "rfm_result.parquet"
RFM_SUMMARY_PATH = SUMMARY_DIR / "rfm_summary.json"
FUNNEL_SUMMARY_PATH = SUMMARY_DIR / "funnel_summary.json"
FUNNEL_DAILY_PATH = SUMMARY_DIR / "funnel_daily.parquet"
CLUSTERING_RESULT_PATH = SUMMARY_DIR / "clustering_result.parquet"
CLUSTERING_SUMMARY_PATH = SUMMARY_DIR / "clustering_summary.json"
ASSOCIATION_RULES_PATH = SUMMARY_DIR / "association_rules.csv"
ASSOCIATION_SUMMARY_PATH = SUMMARY_DIR / "association_summary.json"

# 数据
COLUMNS = ["user_id", "item_id", "category_id", "behavior", "timestamp"]
CHUNK_SIZE = 1_000_000
CLEANING_ENGINE = os.getenv("CLEANING_ENGINE", "polars").lower()
CLEANING_STATS_MODE = os.getenv("CLEANING_STATS_MODE", "fast").lower()
POLARS_MAX_THREADS = os.getenv("POLARS_MAX_THREADS") or os.getenv("CLEANING_THREADS") or "auto"
PARQUET_ROW_GROUP_SIZE = int(os.getenv("PARQUET_ROW_GROUP_SIZE", "1000000"))
VALID_BEHAVIORS = ["pv", "fav", "cart", "buy"]
DATE_RANGE = ("2017-11-25", "2017-12-03")
TIMEZONE = "Asia/Shanghai"

# RFM
ANALYSIS_END_DATE = "2017-12-04"
RFM_SCORE_BINS = 3
RFM_MONETARY_MODE = "category_count"

# K-Means
KMEANS_K_RANGE = (2, 8)
KMEANS_OPTIMAL_K = 5
PLOT_SAMPLE_SIZE = 50_000

# Apriori
APRIORI_SAMPLE_FRACTION = 0.05
APRIORI_MIN_SUPPORT = 0.01
APRIORI_MIN_CONFIDENCE = 0.1
APRIORI_MIN_LIFT = 2.0
APRIORI_MAX_RULES = 30

# 可视化
FIGURE_DPI = 300
FIGURE_SIZE = (12, 8)
DASHBOARD_FIGURE_SIZE = (10, 6)
FONT_FAMILY = "PingFang SC" if platform.system() == "Darwin" else "WenQuanYi Zen Hei"
MATPLOTLIB_STYLE = "seaborn-v0_8-whitegrid"

COLORS = {
    "primary": "#00B4D8",
    "secondary": "#0077B6",
    "accent_warm": "#FF6B35",
    "accent_green": "#06D6A0",
    "dark_bg": "#0D1B2A",
    "light_bg": "#F0F4F8",
    "text_dark": "#1B2838",
    "text_medium": "#475569",
}

BEHAVIOR_COLORS = {
    "pv": "#00B4D8",
    "fav": "#FF6B35",
    "cart": "#0077B6",
    "buy": "#06D6A0",
}

RANDOM_STATE = 42

OUTPUT_DIRECTORIES = [
    CLEANED_DATA_DIR,
    OUTPUT_DIR,
    SUMMARY_DIR,
    RFM_OUTPUT_DIR,
    FUNNEL_OUTPUT_DIR,
    CLUSTERING_OUTPUT_DIR,
    ASSOCIATION_OUTPUT_DIR,
]
