#!/usr/bin/env python3
"""Generate RQ1 label tables and plots from flattened low-output summaries."""

# Simple explanation of this script (step by step):
# 1) Load the summary CSVs produced by `scripts/analyze_rq1_labels.py`.
# 2) Build tidy/wide result tables for each mode/variant/topic/level/metric.
# 3) Compute contrast columns (positive-minus-negative, etc.) for quick reading.
# 4) Generate paper-ready heatmaps and contrast bar plots for each metric and variant.
# 5) Save all tables and figures into one reproducible output folder.

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


DEFAULT_INPUT_DIR = "docs/private/RQ1/RQ1_all_label_analysis"
DEFAULT_OUTPUT_DIR = "docs/private/RQ1/RQ1_all_label_results"
POLARITY_ORDER = ["positive", "neutral", "negative"]
TOPIC_ORDER = [
    "covid_public_health",
    "economy_jobs_trade",
    "foreign_policy_national_security",
    "immigration_border",
    "judiciary_courts",
]
METRIC_ORDER = ["stance_score", "agreement", "legitimacy", "offensiveness", "endorsement"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build RQ1 label tables and plots from summary CSV outputs."
    )
    parser.add_argument(
        "--input-dir",
        default=DEFAULT_INPUT_DIR,
        help="Folder containing outputs from analyze_rq1_labels.py",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Folder where tables/plots will be generated",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite outputs if they already exist",
    )
    return parser.parse_args()


def ensure_output_dir(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        existing_files = list(path.glob("**/*"))
        if existing_files:
            raise FileExistsError(
                f"Output directory already has files: {path}. Use --overwrite."
            )
    path.mkdir(parents=True, exist_ok=True)


def to_ordered_categories(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["persona_polarity"] = pd.Categorical(
        out["persona_polarity"], categories=POLARITY_ORDER, ordered=True
    )
    out["topic"] = pd.Categorical(out["topic"], categories=TOPIC_ORDER, ordered=True)
    out["metric"] = pd.Categorical(out["metric"], categories=METRIC_ORDER, ordered=True)
    return out


def build_tables(summary_by_polarity: pd.DataFrame, summary_overall: pd.DataFrame) -> List[pd.DataFrame]:
    by_pol = summary_by_polarity[summary_by_polarity["metric"].isin(METRIC_ORDER)].copy()

    means_wide = (
        by_pol.pivot_table(
            index=["mode", "variant", "topic", "level", "metric"],
            columns="persona_polarity",
            values="mean",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    for col in POLARITY_ORDER:
        if col not in means_wide.columns:
            means_wide[col] = pd.NA

    means_wide["positive_minus_negative"] = means_wide["positive"] - means_wide["negative"]
    means_wide["positive_minus_neutral"] = means_wide["positive"] - means_wide["neutral"]
    means_wide["neutral_minus_negative"] = means_wide["neutral"] - means_wide["negative"]

    n_wide = (
        by_pol.pivot_table(
            index=["mode", "variant", "topic", "level", "metric"],
            columns="persona_polarity",
            values="n",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    n_wide = n_wide.rename(
        columns={
            "positive": "n_positive",
            "neutral": "n_neutral",
            "negative": "n_negative",
        }
    )

    std_wide = (
        by_pol.pivot_table(
            index=["mode", "variant", "topic", "level", "metric"],
            columns="persona_polarity",
            values="std",
            aggfunc="first",
        )
        .reset_index()
        .rename_axis(None, axis=1)
    )
    std_wide = std_wide.rename(
        columns={
            "positive": "std_positive",
            "neutral": "std_neutral",
            "negative": "std_negative",
        }
    )

    by_topic_polarity = means_wide.merge(
        n_wide,
        on=["mode", "variant", "topic", "level", "metric"],
        how="left",
    ).merge(
        std_wide,
        on=["mode", "variant", "topic", "level", "metric"],
        how="left",
    )

    overall = summary_overall[summary_overall["metric"].isin(METRIC_ORDER)].copy()

    ranking = by_topic_polarity[
        [
            "mode",
            "variant",
            "topic",
            "level",
            "metric",
            "positive_minus_negative",
            "positive_minus_neutral",
            "neutral_minus_negative",
        ]
    ].copy()
    ranking = ranking.sort_values(
        ["mode", "variant", "level", "metric", "positive_minus_negative"],
        ascending=[True, True, True, True, False],
        kind="mergesort",
    )
    ranking["contrast_rank_within_mode_level_metric"] = (
        ranking.groupby(["mode", "variant", "level", "metric"]).cumcount() + 1
    )

    return [by_topic_polarity, overall, ranking]


def plot_heatmaps(by_topic_polarity: pd.DataFrame, outdir: Path) -> List[Path]:
    sns.set_theme(style="whitegrid")
    saved: List[Path] = []
    metrics = [m for m in METRIC_ORDER if m in set(by_topic_polarity["metric"])]
    for mode in sorted(by_topic_polarity["mode"].unique()):
        for variant in sorted(by_topic_polarity[by_topic_polarity["mode"] == mode]["variant"].unique()):
            for level in sorted(by_topic_polarity["level"].unique()):
                for metric in metrics:
                    sub = by_topic_polarity[
                        (by_topic_polarity["mode"] == mode)
                        & (by_topic_polarity["variant"] == variant)
                        & (by_topic_polarity["level"] == level)
                        & (by_topic_polarity["metric"] == metric)
                    ].copy()
                    if sub.empty:
                        continue
                    plot_df = sub.set_index("topic")[POLARITY_ORDER].reindex(TOPIC_ORDER)
                    vmin = None
                    vmax = None
                    cmap = "viridis"
                    if metric == "stance_score":
                        vmin = -1
                        vmax = 1
                        cmap = "coolwarm"
                    elif metric in {"agreement", "legitimacy", "offensiveness", "endorsement"}:
                        vmin = 1
                        vmax = 5
                        cmap = "magma"
                    plt.figure(figsize=(7.5, 3.8))
                    ax = sns.heatmap(
                        plot_df,
                        annot=False,
                        cmap=cmap,
                        vmin=vmin,
                        vmax=vmax,
                        linewidths=0.4,
                        linecolor="white",
                        cbar_kws={"shrink": 0.9},
                    )
                    for row_idx, topic_name in enumerate(plot_df.index):
                        for col_idx, polarity_name in enumerate(plot_df.columns):
                            value = plot_df.loc[topic_name, polarity_name]
                            if pd.notna(value):
                                ax.text(
                                    col_idx + 0.5,
                                    row_idx + 0.5,
                                    f"{float(value):.2f}",
                                    ha="center",
                                    va="center",
                                    color="white",
                                    fontsize=10,
                                    fontweight="bold",
                                )
                    ax.set_title(f"{mode.upper()} · {variant} · {level} · {metric}")
                    ax.set_xlabel("persona_polarity")
                    ax.set_ylabel("topic")
                    out_path = outdir / f"heatmap_{mode}_{variant}_{level}_{metric}.png"
                    plt.tight_layout()
                    plt.savefig(out_path, dpi=220)
                    plt.close()
                    saved.append(out_path)
    return saved


def plot_contrast_bars(by_topic_polarity: pd.DataFrame, outdir: Path) -> List[Path]:
    sns.set_theme(style="whitegrid")
    saved: List[Path] = []
    metrics = [m for m in METRIC_ORDER if m in set(by_topic_polarity["metric"])]
    for mode in sorted(by_topic_polarity["mode"].unique()):
        for variant in sorted(by_topic_polarity[by_topic_polarity["mode"] == mode]["variant"].unique()):
            for level in sorted(by_topic_polarity["level"].unique()):
                for metric in metrics:
                    sub = by_topic_polarity[
                        (by_topic_polarity["mode"] == mode)
                        & (by_topic_polarity["variant"] == variant)
                        & (by_topic_polarity["level"] == level)
                        & (by_topic_polarity["metric"] == metric)
                    ].copy()
                    if sub.empty:
                        continue
                    sub["topic"] = pd.Categorical(sub["topic"], categories=TOPIC_ORDER, ordered=True)
                    sub = sub.sort_values("topic")
                    plt.figure(figsize=(8.2, 3.8))
                    ax = sns.barplot(
                        data=sub,
                        x="topic",
                        y="positive_minus_negative",
                        color="#2b6cb0",
                    )
                    ax.axhline(0, color="black", linewidth=1)
                    ax.set_title(f"{mode.upper()} · {variant} · {level} · {metric} · positive-minus-negative")
                    ax.set_xlabel("topic")
                    ax.set_ylabel("contrast")
                    ax.tick_params(axis="x", rotation=25)
                    out_path = outdir / f"contrast_pos_minus_neg_{mode}_{variant}_{level}_{metric}.png"
                    plt.tight_layout()
                    plt.savefig(out_path, dpi=220)
                    plt.close()
                    saved.append(out_path)
    return saved


def main() -> None:
    args = parse_args()
    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)
    tables_dir = output_dir / "tables"
    plots_dir = output_dir / "plots"
    heatmap_dir = plots_dir / "heatmaps"
    contrast_dir = plots_dir / "contrasts"

    ensure_output_dir(output_dir, args.overwrite)
    tables_dir.mkdir(parents=True, exist_ok=True)
    heatmap_dir.mkdir(parents=True, exist_ok=True)
    contrast_dir.mkdir(parents=True, exist_ok=True)

    summary_by_pol_path = input_dir / "rq1_label_summary_by_polarity.csv"
    summary_overall_path = input_dir / "rq1_label_summary_overall.csv"
    if not summary_by_pol_path.exists() or not summary_overall_path.exists():
        raise FileNotFoundError(
            "Missing summary inputs. Run scripts/analyze_rq1_labels.py first."
        )

    summary_by_pol = pd.read_csv(summary_by_pol_path)
    summary_overall = pd.read_csv(summary_overall_path)

    summary_by_pol = to_ordered_categories(summary_by_pol)
    summary_overall = summary_overall.copy()
    summary_overall["metric"] = pd.Categorical(
        summary_overall["metric"], categories=METRIC_ORDER, ordered=True
    )
    summary_overall["topic"] = pd.Categorical(
        summary_overall["topic"], categories=TOPIC_ORDER, ordered=True
    )

    by_topic_polarity, overall, ranking = build_tables(summary_by_pol, summary_overall)

    by_topic_polarity = by_topic_polarity.sort_values(
        ["mode", "variant", "level", "metric", "topic"], kind="mergesort"
    )
    overall = overall.sort_values(["mode", "variant", "level", "metric", "topic"], kind="mergesort")

    out_by_topic = tables_dir / "rq1_label_table_by_topic_polarity.csv"
    out_overall = tables_dir / "rq1_label_table_overall.csv"
    out_ranking = tables_dir / "rq1_label_topic_contrast_ranking.csv"
    by_topic_polarity.to_csv(out_by_topic, index=False, encoding="utf-8")
    overall.to_csv(out_overall, index=False, encoding="utf-8")
    ranking.to_csv(out_ranking, index=False, encoding="utf-8")

    heatmaps = plot_heatmaps(by_topic_polarity, heatmap_dir)
    contrasts = plot_contrast_bars(by_topic_polarity, contrast_dir)

    manifest = {
        "input_dir": str(input_dir),
        "summary_by_polarity_csv": str(summary_by_pol_path),
        "summary_overall_csv": str(summary_overall_path),
        "output_dir": str(output_dir),
        "tables": {
            "rq1_label_table_by_topic_polarity": str(out_by_topic),
            "rq1_label_table_overall": str(out_overall),
            "rq1_label_topic_contrast_ranking": str(out_ranking),
        },
        "plots": {
            "heatmaps_count": len(heatmaps),
            "contrasts_count": len(contrasts),
        },
        "filters": {
            "variants": sorted(by_topic_polarity["variant"].dropna().unique().tolist()),
            "metrics": METRIC_ORDER,
            "topics": TOPIC_ORDER,
            "polarities": POLARITY_ORDER,
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Tables written: {tables_dir}")
    print(f"Heatmaps written: {len(heatmaps)}")
    print(f"Contrast bars written: {len(contrasts)}")
    print(f"Output root: {output_dir}")


if __name__ == "__main__":
    main()
