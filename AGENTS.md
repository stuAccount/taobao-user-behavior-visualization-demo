# AGENTS.md — 电商用户行为分析项目引导文件

> 本文件供 AI 编程助手阅读，用于引导其完成整个项目的代码实现。
> 请严格按照本文件的结构、技术栈和代码规范要求执行。

---

## 1. 项目概述

### 1.1 背景

这是一个大学课程项目——"大数据可视化分析"课程的最终汇报。主题为**电商用户行为分析**，基于阿里天池的 UserBehavior（淘宝用户行为）数据集。

前期的选题汇报、过程汇报（数据清洗与存储）、统计设计汇报均已完成（PPT 和讲稿在 `../课程汇报/` 目录），现在需要实现完整的 Python 代码，生成可视化图表和交互仪表盘，用于最终的课程展示。

### 1.2 核心目标

- 对淘宝用户行为数据进行清洗、分析和可视化
- 实现 RFM 用户价值分层、行为漏斗分析、K-Means 聚类分群、Apriori 关联规则四个分析模块
- 输出高质量静态图片（用于 PPT）和 Streamlit 交互仪表盘（用于现场演示）
- 提供 Docker 部署方案和一键运行脚本

### 1.3 最终交付物

| 交付物 | 说明 |
|--------|------|
| 数据清洗脚本 | 去重、类型转换、异常过滤、时间解析 |
| RFM 分析报告 | 用户价值分层，含评分分布图、分层占比图 |
| 漏斗分析报告 | pv→fav→cart→buy 各步转化率与流失率 |
| K-Means 聚类分析 | 用户分群 + 雷达图展示群体画像 |
| Apriori 关联规则（可选） | 商品共现关联，抽样后运行 |
| 静态高清 PNG 图片 | 所有分析模块的核心可视化图表，保存到 `output/` |
| Streamlit 仪表盘 | 交互式可视化，用于现场演示 |
| Docker 配置 | Dockerfile + docker-compose.yml |
| 一键运行脚本 | `run.sh`，执行全流程分析 |

---

## 2. 数据集

### 2.1 数据信息

- **名称**：UserBehavior（淘宝用户行为数据集）
- **来源**：阿里天池
- **Kaggle 下载（推荐）**：https://www.kaggle.com/datasets/gogokerry/taobao-user-behavior
- **天池下载（备用）**：https://tianchi.aliyun.com/dataset/649
- **文件大小**：约 3.67GB（CSV）
- **文件格式**：CSV，逗号分隔，**无表头**
- **记录数**：约 1 亿条
- **用户数**：100 万+
- **商品数**：500 万+
- **类目数**：5000+

### 2.2 字段定义

| 列序号 | 字段名 | 类型 | 说明 |
|--------|--------|------|------|
| 1 | user_id | int | 用户 ID（已脱敏） |
| 2 | item_id | int | 商品 ID（已脱敏） |
| 3 | category_id | int | 商品类目 ID（已脱敏） |
| 4 | behavior | str | 行为类型：`pv`（浏览）、`fav`（收藏）、`cart`（加购）、`buy`（购买） |
| 5 | timestamp | int | Unix 时间戳（秒） |

### 2.3 时间范围

2017-11-25 至 2017-12-03（共 9 天）

### 2.4 数据文件放置

数据文件下载后放到 `data/` 目录：

```
data/
└── UserBehavior.csv    ← 原始数据文件（无表头的 CSV）
```

**注意**：原始 CSV 无表头，读取时需要手动指定列名：

```python
columns = ["user_id", "item_id", "category_id", "behavior", "timestamp"]
df = pd.read_csv("data/UserBehavior.csv", names=columns)
```

### 2.5 大文件处理策略

数据量约 1 亿条，需注意内存管理：

- 服务器有 64GB 内存，可以加载全量数据
- 使用 `chunksize` 参数分块读取处理（推荐 100 万条/块）
- 清洗后的中间结果保存到 `data/cleaned/` 供后续分析复用
- Apriori 关联规则必须抽样后运行（建议抽样 5%-10% 的用户）

---

## 3. 项目目录结构

```
电商用户行为分析/                    ← 项目根目录（Git 仓库）
├── AGENTS.md                        ← 本文件（AI 引导文档）
├── requirements.txt                 ← Python 依赖
├── run.sh                           ← 一键运行脚本
├── Dockerfile                       ← Docker 构建文件
├── docker-compose.yml               ← Docker Compose 配置
├── .gitignore
│
├── analysis/                        ← Python 源代码
│   ├── __init__.py
│   ├── config.py                    ← 全局配置（路径、颜色、参数）
│   ├── data_cleaning.py             ← 数据清洗模块
│   ├── rfm_analysis.py              ← RFM 用户价值分析
│   ├── funnel_analysis.py           ← 行为漏斗分析
│   ├── clustering.py                ← K-Means 聚类分析
│   ├── association_rules.py         ← Apriori 关联规则（可选）
│   ├── visualization.py             ← 通用可视化函数（图表样式、配色）
│   └── utils.py                     ← 工具函数（日志、进度条等）
│
├── dashboard/                       ← Streamlit 仪表盘
│   ├── app.py                       ← Streamlit 主入口
│   └── pages/                       ← 多页面（按分析模块分）
│       ├── rfm.py
│       ├── funnel.py
│       ├── clustering.py
│       └── association.py
│
├── data/                            ← 数据文件（不进 Git）
│   ├── UserBehavior.csv             ← 原始数据（手动下载）
│   └── cleaned/                     ← 清洗后的中间数据
│
└── output/                          ← 输出文件（图片、报告）
    ├── rfm/                         ← RFM 分析图表
    ├── funnel/                      ← 漏斗分析图表
    ├── clustering/                  ← 聚类分析图表
    └── association/                 ← 关联规则图表
```

---

## 4. 技术栈

### 4.1 Python 环境

- Python 3.10+
- pip 管理依赖

### 4.2 核心依赖

```
pandas>=2.0
numpy>=1.24
matplotlib>=3.7
seaborn>=0.12
plotly>=5.15
scikit-learn>=1.3
mlxtend>=0.22          # Apriori（可选）
streamlit>=1.28
```

### 4.3 辅助依赖

```
joblib                 # 模型/中间结果持久化
tqdm                   # 进度条
pyarrow                # 高性能 parquet 读写（可选）
```

### 4.4 Docker

- 基于 `python:3.11-slim` 镜像
- docker-compose 一键启动 Streamlit 仪表盘
- 挂载 `data/` 和 `output/` 卷

---

## 5. 模块实现要求

### 5.1 数据清洗（`analysis/data_cleaning.py`）

按以下步骤执行，每步打印进度和统计信息：

1. **读取数据**：分块读取（chunksize=1_000_000），指定列名
2. **去重**：基于 `(user_id, item_id, timestamp)` 三字段去重（预期去重率约 15%）
3. **过滤异常值**：剔除 behavior 不在 `["pv", "fav", "cart", "buy"]` 中的记录
4. **时间解析**：将 Unix 时间戳转为 `datetime`（UTC+8），提取 `date`、`hour`、`weekday` 字段
5. **类型优化**：`user_id`/`item_id`/`category_id` 转 `int32`，`behavior` 转 `category` 类型
6. **保存清洗结果**：输出到 `data/cleaned/` 目录

**关键输出**：清洗前后记录数对比、各行为类型数量统计、时间范围验证

### 5.2 RFM 分析（`analysis/rfm_analysis.py`）

**RFM 定义**（基于购买行为 buy）：

| 指标 | 定义 | 说明 |
|------|------|------|
| R（Recency） | 最近一次购买距分析截止日的天数 | 越小越好 |
| F（Frequency） | 分析期内的购买次数 | 越多越好 |
| M（Monetary） | 分析期内的购买金额 | 本数据集无金额字段，用购买次数或购买类目数代替 |

**打分与分层**：
- 按 R/F/M 各自的中位数或分位数打分（1-3 分或高低二分）
- 组合为 8 类用户标签：重要价值、重要发展、重要保持、重要挽留、一般价值、一般发展、一般保持、一般挽留

**可视化输出**：R/F/M 分布直方图、用户分层占比饼图/环形图、各层级 RFM 均值对比柱状图

### 5.3 漏斗分析（`analysis/funnel_analysis.py`）

**漏斗层级**：`pv → fav → cart → buy`

**计算内容**：
- 各行为类型的独立用户数（UV）和总行为次数
- 逐级转化率
- 按日期/时段的转化率趋势

**可视化输出**：经典漏斗图（水平条形）、转化率桑基图（Plotly Sankey）、日维度转化率趋势折线图

### 5.4 K-Means 聚类（`analysis/clustering.py`）

**特征构建**：对 R/F/M 值做标准化（StandardScaler），可选加入其他行为特征

**建模**：
- 肘部法则确定最优 K 值（建议 K=4~6）
- 运行 K-Means 聚类

**可视化输出**：肘部法则图、各聚类 RFM 均值雷达图（核心图表）、聚类散点图（PCA 降维）、各群体用户数占比

**画像标签**：为每个聚类群体总结特征标签

### 5.5 Apriori 关联规则（`analysis/association_rules.py`，可选）

**前置处理**：必须抽样 5%-10% 购买用户，用 category_id 构建事务数据

**参数建议**：min_support=0.01, min_confidence=0.1, min_lift=2.0

**可视化输出**：关联规则网络图、支持度-置信度散点图、Top-N 规则表格

---

## 6. 可视化规范

### 6.1 配色方案

```python
COLORS = {
    "primary":     "#00B4D8",   # 青色，主色调
    "secondary":   "#0077B6",   # 深蓝
    "accent_warm": "#FF6B35",   # 暖橙，强调色
    "accent_green":"#06D6A0",   # 翠绿
    "dark_bg":     "#0D1B2A",   # 深蓝黑，深色背景
    "light_bg":    "#F0F4F8",   # 浅灰蓝，浅色背景
    "text_dark":   "#1B2838",   # 深色文字
    "text_medium": "#475569",   # 中等灰度文字
}

BEHAVIOR_COLORS = {
    "pv":   "#00B4D8",   # 浏览 - 青色
    "fav":  "#FF6B35",   # 收藏 - 暖橙
    "cart": "#0077B6",   # 加购 - 深蓝
    "buy":  "#06D6A0",   # 购买 - 翠绿
}
```

### 6.2 图表规范

- **语言**：所有标题、坐标轴标签、图例均使用**中文**
- **字体**：macOS 用 `PingFang SC`；Docker/Linux 用 `WenQuanYi Zen Hei`
- **分辨率**：静态图片保存为 300 DPI 的 PNG
- **尺寸**：单图 12x8 或 14x8 英寸
- **保存路径**：`output/{module}/` 子目录
- **matplotlib 后端**：非交互环境使用 `Agg` 后端

---

## 7. Streamlit 仪表盘

### 7.1 结构

```
dashboard/
├── app.py              ← 主入口，侧边栏导航
└── pages/
    ├── rfm.py          ← RFM 分析交互页
    ├── funnel.py       ← 漏斗分析交互页
    ├── clustering.py   ← 聚类分析交互页
    └── association.py  ← 关联规则交互页（可选）
```

### 7.2 交互功能

- **首页**：数据概览卡片（总记录数、用户数、商品数、时间范围）
- **RFM 页**：可调打分阈值滑块，实时重新分层
- **漏斗页**：可选日期范围，Plotly 桑基图
- **聚类页**：可选 K 值滑块，雷达图交互展示
- **关联页**：可调 support/confidence 阈值

### 7.3 数据加载

- 加载清洗后的中间数据（`data/cleaned/`），使用 `@st.cache_data` 缓存

---

## 8. Docker 配置

### 8.1 Dockerfile

- 基础镜像：`python:3.11-slim`
- 安装中文字体（`fonts-wqy-zenhei`）
- 安装 Python 依赖
- 暴露端口 8501

### 8.2 docker-compose.yml

```yaml
services:
  dashboard:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./data:/app/data
      - ./output:/app/output
    environment:
      - STREAMLIT_SERVER_HEADLESS=true
```

---

## 9. 一键运行脚本（run.sh）

1. 检查 Python 环境和依赖
2. 检查数据文件（`data/UserBehavior.csv`）
3. 运行数据清洗
4. 依次运行各分析模块
5. 提示输出文件位置
6. （可选）启动 Streamlit 仪表盘

---

## 10. 代码规范

- **所有注释使用中文**，函数必须有中文 docstring
- 关键步骤打印日志和耗时
- 每个模块既可独立运行（`if __name__ == "__main__"`），也可被导入
- 全局配置集中在 `config.py`
- 输出图片命名：`{module}_{chart_type}.png`
- 数据文件不存在时给出清晰的下载指引
- 设置随机种子 `random_state=42` 确保可复现

---

## 11. 配置参数参考（config.py）

```python
# 路径
RAW_DATA_PATH = "data/UserBehavior.csv"
CLEANED_DATA_DIR = "data/cleaned"
OUTPUT_DIR = "output"

# 数据
CHUNK_SIZE = 1_000_000
VALID_BEHAVIORS = ["pv", "fav", "cart", "buy"]
DATE_RANGE = ("2017-11-25", "2017-12-03")

# RFM
RFM_SCORE_BINS = 3

# K-Means
KMEANS_K_RANGE = (2, 8)
KMEANS_OPTIMAL_K = 5

# Apriori
APRIORI_SAMPLE_FRACTION = 0.05
APRIORI_MIN_SUPPORT = 0.01
APRIORI_MIN_CONFIDENCE = 0.1
APRIORI_MIN_LIFT = 2.0

# 可视化
FIGURE_DPI = 300
FIGURE_SIZE = (12, 8)
FONT_FAMILY = "PingFang SC"    # macOS; Docker 中改为 "WenQuanYi Zen Hei"
```

---

## 12. 实现优先级

| 优先级 | 模块 | 原因 |
|--------|------|------|
| P0 | 数据清洗 | 所有后续分析的基础 |
| P0 | RFM 分析 | 核心分析模块，汇报重点 |
| P0 | 漏斗分析 | 核心分析模块，直观易理解 |
| P1 | K-Means 聚类 | 雷达图视觉效果好 |
| P1 | Streamlit 仪表盘 | 现场演示必备 |
| P2 | Apriori 关联规则 | 讲稿中提及但可选 |
| P2 | Docker 配置 | 方便部署但非必须 |
| P3 | run.sh 脚本 | 便利性工具 |

---

## 13. 注意事项

1. **数据无金额字段**：M 用购买次数或购买类目数代替
2. **中文字体**：matplotlib 必须正确配置，这是最常见问题
3. **内存管理**：清洗阶段用分块读取，分析阶段用聚合数据
4. **时间戳时区**：使用 UTC+8（中国标准时间）
5. **可复现性**：`random_state=42`
6. **汇报一致性**：分析方法和结论不能与已完成的三次汇报矛盾

---

## 14. 相关参考

- 课程汇报 PPT 和讲稿：`../课程汇报/` 目录
- Kaggle 数据集：https://www.kaggle.com/datasets/gogokerry/taobao-user-behavior
- 天池数据集：https://tianchi.aliyun.com/dataset/649

---

## 15. 按需容器工作流（重要）

### 15.1 场景说明

服务器是**随用随销的容器**，每次启动都是全新环境，没有持久化存储。因此需要将工作流分为两个独立阶段，避免每次都重新下载 3.67GB 数据和跑分析。

### 15.2 两阶段工作流

```
┌─────────────────────────────────────────────────────────┐
│  阶段 A：生成分析结果（只在首次或修改代码后执行一次）        │
│                                                         │
│  1. SSH 到服务器                                         │
│  2. git clone 项目代码                                   │
│  3. ./scripts/setup_and_analyze.sh                       │
│     → 自动安装依赖                                       │
│     → 下载数据集（Kaggle API）                            │
│     → 运行数据清洗                                       │
│     → 运行全部分析模块                                    │
│     → 生成所有可视化图片                                   │
│  4. 将 output/ 和 data/cleaned/ 打包下载到本地             │
│     → scp 或 tar 打包                                    │
│  5. 销毁服务器                                           │
└─────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────┐
│  阶段 B：演示展示（线下汇报时使用）                        │
│                                                         │
│  方案 B1：本地演示（推荐）                                 │
│    → 用本地已有的 output/ 图片贴进 PPT                     │
│    → 或用本地 Python 环境启动 Streamlit 仪表盘             │
│                                                         │
│  方案 B2：服务器演示（需要在线交互时）                      │
│    → 启动新服务器                                        │
│    → git clone + 上传之前打包的数据和结果                   │
│    → ./scripts/demo.sh                                   │
│      → 安装依赖（快速，不需要下载数据）                     │
│      → 直接用已有的 cleaned 数据启动 Streamlit             │
└─────────────────────────────────────────────────────────┘
```

### 15.3 需要实现的脚本

#### `scripts/setup_and_analyze.sh`（阶段 A：完整流程）

```bash
#!/bin/bash
# 阶段 A：在按需容器上执行一次完整的数据下载 + 分析流程
# 适用于：首次运行 / 修改分析代码后重新生成结果
set -e

echo "========== [1/5] 安装 Python 依赖 =========="
pip install -r requirements.txt

echo "========== [2/5] 下载数据集 =========="
# 使用 Kaggle API 下载（需要 KAGGLE_USERNAME 和 KAGGLE_KEY 环境变量）
# 如果已存在则跳过
if [ ! -f data/UserBehavior.csv ]; then
    mkdir -p data
    pip install kaggle
    kaggle datasets download -d gogokerry/taobao-user-behavior -p data/ --unzip
    # 如果下载的是 zip，解压后移到正确位置
    if [ -f data/taobao-user-behavior.zip ]; then
        unzip -o data/taobao-user-behavior.zip -d data/
        rm data/taobao-user-behavior.zip
    fi
    echo "✅ 数据下载完成"
else
    echo "⏭️  数据文件已存在，跳过下载"
fi

echo "========== [3/5] 数据清洗 =========="
python -m analysis.data_cleaning

echo "========== [4/5] 运行分析模块 =========="
python -m analysis.rfm_analysis
python -m analysis.funnel_analysis
python -m analysis.clustering
# python -m analysis.association_rules  # 可选，取消注释启用

echo "========== [5/5] 打包结果 =========="
tar -czf results_bundle.tar.gz output/ data/cleaned/
echo "✅ 全部完成！结果已打包为 results_bundle.tar.gz"
echo "   请用以下命令下载到本地："
echo "   scp <server>:<path>/results_bundle.tar.gz ./"
```

#### `scripts/demo.sh`（阶段 B：仅启动演示）

```bash
#!/bin/bash
# 阶段 B：在已有分析结果的前提下，快速启动 Streamlit 演示仪表盘
# 适用于：线下汇报现场演示 / 查看已有结果
set -e

echo "========== 安装依赖 =========="
pip install -r requirements.txt

# 检查是否有清洗后的数据
if [ ! -d data/cleaned ]; then
    echo "❌ 未找到 data/cleaned/ 目录"
    echo "   请先运行 scripts/setup_and_analyze.sh 或上传之前打包的结果"
    echo "   解压命令：tar -xzf results_bundle.tar.gz"
    exit 1
fi

echo "========== 启动 Streamlit 仪表盘 =========="
streamlit run dashboard/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true
```

#### `scripts/download_data.sh`（独立的数据下载脚本）

```bash
#!/bin/bash
# 独立的数据下载脚本，可单独执行
# 支持 Kaggle API 和直接 URL 两种方式
set -e

mkdir -p data

if [ -f data/UserBehavior.csv ]; then
    echo "⏭️  数据文件已存在（$(du -h data/UserBehavior.csv | cut -f1)），跳过下载"
    exit 0
fi

echo "开始下载 UserBehavior 数据集（约 3.67GB）..."

# 方式 1：Kaggle API（推荐，需要先配置 kaggle.json）
if command -v kaggle &> /dev/null || [ -f ~/.kaggle/kaggle.json ]; then
    pip install -q kaggle
    kaggle datasets download -d gogokerry/taobao-user-behavior -p data/ --unzip
# 方式 2：直接 curl（备用）
else
    echo "未检测到 Kaggle CLI，尝试直接下载..."
    curl -L -o data/taobao-user-behavior.zip \
        "https://www.kaggle.com/api/v1/datasets/download/gogokerry/taobao-user-behavior"
    unzip -o data/taobao-user-behavior.zip -d data/
    rm -f data/taobao-user-behavior.zip
fi

# 验证文件
if [ -f data/UserBehavior.csv ]; then
    LINES=$(wc -l < data/UserBehavior.csv)
    SIZE=$(du -h data/UserBehavior.csv | cut -f1)
    echo "✅ 下载完成：data/UserBehavior.csv（$LINES 行，$SIZE）"
else
    echo "❌ 下载后未找到 UserBehavior.csv，请检查 data/ 目录内容"
    ls -la data/
    exit 1
fi
```

### 15.4 结果同步方式

在服务器上生成结果后，需要下载到本地保存：

```bash
# 在服务器上打包
tar -czf results_bundle.tar.gz output/ data/cleaned/

# 从服务器下载到本地
scp user@server:/path/to/results_bundle.tar.gz ./

# 本地解压
tar -xzf results_bundle.tar.gz
```

### 15.5 目录结构更新

```
电商用户行为分析/
├── ...（已有文件）
├── scripts/                          ← 运维脚本
│   ├── setup_and_analyze.sh          ← 阶段 A：完整流程（下载+清洗+分析+打包）
│   ├── demo.sh                       ← 阶段 B：仅启动演示仪表盘
│   └── download_data.sh              ← 独立数据下载脚本
└── results_bundle.tar.gz             ← 打包的分析结果（可选，从服务器下载）
```

### 15.6 Kaggle API 配置

在服务器上需要先配置 Kaggle API 才能下载数据：

```bash
# 1. 创建 kaggle 配置目录
mkdir -p ~/.kaggle

# 2. 写入 API 密钥（从 https://www.kaggle.com/settings 获取）
echo '{"username":"YOUR_USERNAME","key":"YOUR_API_KEY"}' > ~/.kaggle/kaggle.json
chmod 600 ~/.kaggle/kaggle.json

# 3. 或者通过环境变量传入
export KAGGLE_USERNAME=YOUR_USERNAME
export KAGGLE_KEY=YOUR_API_KEY
```
