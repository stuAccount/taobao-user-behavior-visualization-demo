"""项目通用可视化工具。"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from analysis import config


def configure_matplotlib() -> None:
    """配置全局绘图样式。"""
    plt.style.use(config.MATPLOTLIB_STYLE)
    plt.rcParams["font.family"] = config.FONT_FAMILY
    plt.rcParams["axes.unicode_minus"] = False
    plt.rcParams["figure.dpi"] = config.FIGURE_DPI
    plt.rcParams["savefig.dpi"] = config.FIGURE_DPI


def create_figure(size: tuple[int, int] | tuple[float, float] | None = None):
    """创建统一尺寸的图表画布。"""
    configure_matplotlib()
    return plt.subplots(figsize=size or config.FIGURE_SIZE)


def save_figure(fig: plt.Figure, output_path: Path) -> Path:
    """保存图表并自动创建目录。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
    return output_path


def get_behavior_color(behavior: str) -> str:
    """获取行为对应颜色。"""
    return config.BEHAVIOR_COLORS.get(behavior, config.COLORS["primary"])


def annotate_bars(ax: plt.Axes, values: Iterable[float], fmt: str = "{:.2f}") -> None:
    """在柱状图顶部标注数值。"""
    for patch, value in zip(ax.patches, values):
        ax.text(
            patch.get_x() + patch.get_width() / 2,
            patch.get_height(),
            fmt.format(value),
            ha="center",
            va="bottom",
            fontsize=10,
            color=config.COLORS["text_dark"],
        )


def radar_angles(num_vars: int) -> np.ndarray:
    """计算雷达图角度。"""
    angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False)
    return np.concatenate([angles, [angles[0]]])
