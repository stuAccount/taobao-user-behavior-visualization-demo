"""Apriori 商品类目关联规则分析模块。"""

from __future__ import annotations

from itertools import combinations

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder

from analysis import config
from analysis.utils import ensure_directories, get_logger, load_cleaned_data, log_step, save_json
from analysis.visualization import create_figure, save_figure


def build_transactions(
    df: pd.DataFrame,
    sample_fraction: float = config.APRIORI_SAMPLE_FRACTION,
) -> list[list[str]]:
    """基于购买用户抽样构建类目事务。"""
    buy_df = df[df["behavior"].astype(str) == "buy"].copy()
    if buy_df.empty:
        return []

    users = buy_df["user_id"].drop_duplicates()
    if 0 < sample_fraction < 1 and len(users) > 20:
        users = users.sample(frac=sample_fraction, random_state=config.RANDOM_STATE)
    sampled_df = buy_df[buy_df["user_id"].isin(users)]
    transactions = (
        sampled_df.groupby("user_id")["category_id"]
        .apply(lambda values: sorted({str(value) for value in values}))
        .tolist()
    )
    return [transaction for transaction in transactions if len(transaction) >= 2]


def mine_association_rules(
    transactions: list[list[str]],
    min_support: float = config.APRIORI_MIN_SUPPORT,
    min_confidence: float = config.APRIORI_MIN_CONFIDENCE,
    min_lift: float = config.APRIORI_MIN_LIFT,
) -> pd.DataFrame:
    """挖掘 Apriori 关联规则。"""
    if len(transactions) < 2:
        return empty_rules_df()

    encoder = TransactionEncoder()
    encoded = encoder.fit(transactions).transform(transactions)
    basket_df = pd.DataFrame(encoded, columns=encoder.columns_)
    frequent_itemsets = apriori(basket_df, min_support=min_support, use_colnames=True)
    if frequent_itemsets.empty:
        return empty_rules_df()

    rules = association_rules(frequent_itemsets, metric="confidence", min_threshold=min_confidence)
    if rules.empty:
        return empty_rules_df()

    rules = rules[rules["lift"] >= min_lift].copy()
    if rules.empty:
        return empty_rules_df()

    rules["antecedents"] = rules["antecedents"].apply(lambda items: ",".join(sorted(items)))
    rules["consequents"] = rules["consequents"].apply(lambda items: ",".join(sorted(items)))
    columns = ["antecedents", "consequents", "support", "confidence", "lift"]
    return rules[columns].sort_values(["lift", "confidence", "support"], ascending=False).head(config.APRIORI_MAX_RULES)


def empty_rules_df() -> pd.DataFrame:
    """返回空规则表。"""
    return pd.DataFrame(columns=["antecedents", "consequents", "support", "confidence", "lift"])


def fallback_pair_rules(transactions: list[list[str]]) -> pd.DataFrame:
    """在样本极少时生成用于演示的二项共现规则。"""
    if not transactions:
        return empty_rules_df()
    transaction_count = len(transactions)
    item_counts: dict[str, int] = {}
    pair_counts: dict[tuple[str, str], int] = {}
    for transaction in transactions:
        unique_items = sorted(set(transaction))
        for item in unique_items:
            item_counts[item] = item_counts.get(item, 0) + 1
        for left, right in combinations(unique_items, 2):
            pair_counts[(left, right)] = pair_counts.get((left, right), 0) + 1

    rows = []
    for (left, right), count in pair_counts.items():
        support = count / transaction_count
        confidence = count / item_counts[left]
        consequent_support = item_counts[right] / transaction_count
        lift = confidence / consequent_support if consequent_support else 0
        rows.append(
            {
                "antecedents": left,
                "consequents": right,
                "support": support,
                "confidence": confidence,
                "lift": lift,
            }
        )
    return pd.DataFrame(rows).sort_values(["lift", "confidence", "support"], ascending=False).head(config.APRIORI_MAX_RULES) if rows else empty_rules_df()


def plot_rules_scatter(rules_df: pd.DataFrame) -> None:
    """绘制支持度-置信度散点图。"""
    if rules_df.empty:
        return
    fig, ax = create_figure()
    scatter = ax.scatter(
        rules_df["support"],
        rules_df["confidence"],
        s=(rules_df["lift"].clip(lower=1) * 40),
        c=rules_df["lift"],
        cmap="viridis",
        alpha=0.75,
    )
    fig.colorbar(scatter, ax=ax, label="提升度")
    ax.set_title("关联规则支持度-置信度分布")
    ax.set_xlabel("支持度")
    ax.set_ylabel("置信度")
    save_figure(fig, config.ASSOCIATION_OUTPUT_DIR / "association_scatter.png")


def plot_rules_network(rules_df: pd.DataFrame) -> None:
    """绘制关联规则网络图。"""
    if rules_df.empty:
        return
    graph = nx.DiGraph()
    top_rules = rules_df.head(15)
    for _, row in top_rules.iterrows():
        graph.add_edge(row["antecedents"], row["consequents"], weight=row["lift"])

    fig, ax = create_figure((12, 9))
    pos = nx.spring_layout(graph, seed=config.RANDOM_STATE, k=0.8)
    weights = [graph[u][v]["weight"] for u, v in graph.edges()]
    nx.draw_networkx_nodes(graph, pos, ax=ax, node_color=config.COLORS["primary"], node_size=1200, alpha=0.86)
    nx.draw_networkx_edges(graph, pos, ax=ax, width=[max(1, weight) for weight in weights], edge_color=config.COLORS["accent_warm"], arrows=True, alpha=0.65)
    nx.draw_networkx_labels(graph, pos, ax=ax, font_size=9)
    ax.set_title("Top 关联规则网络图")
    ax.axis("off")
    save_figure(fig, config.ASSOCIATION_OUTPUT_DIR / "association_network.png")


def save_top_rules_table(rules_df: pd.DataFrame) -> None:
    """保存 Top-N 规则表格。"""
    config.ASSOCIATION_RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    rules_df.to_csv(config.ASSOCIATION_RULES_PATH, index=False)


def summarize_rules(transactions: list[list[str]], rules_df: pd.DataFrame, used_fallback: bool) -> dict[str, object]:
    """生成关联规则摘要。"""
    return {
        "transaction_count": int(len(transactions)),
        "rule_count": int(len(rules_df)),
        "used_fallback": bool(used_fallback),
        "top_rules": rules_df.round(4).to_dict(orient="records"),
    }


def run_association_rules() -> tuple[pd.DataFrame, dict[str, object]]:
    """执行 Apriori 关联规则分析。"""
    ensure_directories()
    logger = get_logger("association_rules")
    with log_step(logger, "加载清洗后数据"):
        df = load_cleaned_data(columns=["user_id", "category_id", "behavior"])
    with log_step(logger, "构建购买事务"):
        transactions = build_transactions(df)
    with log_step(logger, "挖掘关联规则"):
        rules_df = mine_association_rules(transactions)
        used_fallback = False
        if rules_df.empty and len(transactions) > 0:
            logger.info("Apriori 未生成规则，使用二项共现规则作为安全回退。")
            rules_df = fallback_pair_rules(transactions)
            used_fallback = not rules_df.empty
    with log_step(logger, "保存关联规则结果"):
        save_top_rules_table(rules_df)
        summary = summarize_rules(transactions, rules_df, used_fallback)
        save_json(summary, config.ASSOCIATION_SUMMARY_PATH)
    with log_step(logger, "生成关联规则可视化图表"):
        plot_rules_scatter(rules_df)
        plot_rules_network(rules_df)
    return rules_df, summary


def main() -> None:
    """脚本入口。"""
    rules_df, summary = run_association_rules()
    print("Apriori 关联规则分析完成。")
    print(f"事务数：{summary['transaction_count']:,}")
    print(f"规则数：{summary['rule_count']:,}")
    if rules_df.empty:
        print("当前样本未生成有效关联规则，流程已安全结束。")
    else:
        print(rules_df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
