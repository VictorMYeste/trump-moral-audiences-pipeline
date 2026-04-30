#!/usr/bin/env python3
"""Build synthetic topic distributions and PEW-vs-synthetic alignment metrics for RQ3."""

# Simple explanation of this script (step by step):
# 1) Read PEW weighted topic summaries from `data/interim/rq3/`.
# 2) Read synthetic stance outputs (tweet-level + bundle-level flat tables).
# 3) Build synthetic topic distributions in comparable positive/negative/neutral percentages.
# 4) Compare PEW vs synthetic by topic for each (mode, variant, level) configuration.
# 5) Export alignment metrics: correlation, absolute error, and rank-agreement diagnostics.

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


PEW_TOPIC_SUMMARY_DEFAULT = "data/interim/rq3/pew_weighted_topic_summary.csv"
SYN_BUNDLE_DEFAULT = "docs/private/RQ1/RQ1_all_label_analysis/rq1_bundle_labels_flat.csv"
SYN_TWEET_DEFAULT = "docs/private/RQ1/RQ1_all_label_analysis/rq1_tweet_labels_flat.csv"
OUTPUT_DIR_DEFAULT = "data/interim/rq3"

STANCE_TO_BUCKET = {
    "support": "positive",
    "reject": "negative",
    "neutral": "neutral",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compute RQ3 alignment between PEW weighted topic distributions and "
            "synthetic audience topic distributions."
        )
    )
    parser.add_argument(
        "--pew-topic-summary",
        default=PEW_TOPIC_SUMMARY_DEFAULT,
        help=f"PEW weighted topic summary CSV (default: {PEW_TOPIC_SUMMARY_DEFAULT})",
    )
    parser.add_argument(
        "--synthetic-bundle",
        default=SYN_BUNDLE_DEFAULT,
        help=f"Synthetic bundle flat CSV (default: {SYN_BUNDLE_DEFAULT})",
    )
    parser.add_argument(
        "--synthetic-tweet",
        default=SYN_TWEET_DEFAULT,
        help=f"Synthetic tweet flat CSV (default: {SYN_TWEET_DEFAULT})",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIR_DEFAULT,
        help=f"Output directory (default: {OUTPUT_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output files",
    )
    return parser.parse_args()


def safe_pearson(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 2:
        return None
    x_arr = np.asarray(x, dtype=float)
    y_arr = np.asarray(y, dtype=float)
    if float(np.nanstd(x_arr)) <= 0.0 or float(np.nanstd(y_arr)) <= 0.0:
        return None
    return float(np.corrcoef(x_arr, y_arr)[0, 1])


def safe_spearman(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or len(x) < 2:
        return None
    rank_x = pd.Series(x).rank(method="average", ascending=True).to_numpy()
    rank_y = pd.Series(y).rank(method="average", ascending=True).to_numpy()
    return safe_pearson(rank_x.tolist(), rank_y.tolist())


def mean_abs_error(x: Sequence[float], y: Sequence[float]) -> Optional[float]:
    if len(x) != len(y) or not x:
        return None
    diffs = [abs(float(a) - float(b)) for a, b in zip(x, y)]
    return float(sum(diffs) / len(diffs))


def rank_agreement_stats(
    topics: Sequence[str],
    pew_vals: Sequence[float],
    syn_vals: Sequence[float],
) -> Dict[str, object]:
    if not topics or len(topics) != len(pew_vals) or len(pew_vals) != len(syn_vals):
        return {
            "mean_abs_rank_diff": None,
            "top1_topic_match": None,
            "exact_rank_order_match": None,
        }

    df = pd.DataFrame(
        {
            "topic": list(topics),
            "pew_value": list(pew_vals),
            "syn_value": list(syn_vals),
        }
    )
    # Higher value = more positive support, so descending rank.
    df["pew_rank"] = df["pew_value"].rank(method="average", ascending=False)
    df["syn_rank"] = df["syn_value"].rank(method="average", ascending=False)
    mean_abs_rank_diff = float((df["pew_rank"] - df["syn_rank"]).abs().mean())

    pew_sorted = df.sort_values(["pew_value", "topic"], ascending=[False, True], kind="mergesort")
    syn_sorted = df.sort_values(["syn_value", "topic"], ascending=[False, True], kind="mergesort")
    top1_topic_match = bool(pew_sorted.iloc[0]["topic"] == syn_sorted.iloc[0]["topic"])
    exact_rank_order_match = bool(list(pew_sorted["topic"]) == list(syn_sorted["topic"]))

    return {
        "mean_abs_rank_diff": mean_abs_rank_diff,
        "top1_topic_match": top1_topic_match,
        "exact_rank_order_match": exact_rank_order_match,
    }


def normalize_stance(value: object) -> str:
    text = str(value or "").strip().lower()
    if text in STANCE_TO_BUCKET:
        return text
    return ""


def build_synthetic_topic_distribution(
    syn_bundle_path: Path,
    syn_tweet_path: Path,
    target_topics: Sequence[str],
) -> pd.DataFrame:
    bundle = pd.read_csv(syn_bundle_path)
    tweet = pd.read_csv(syn_tweet_path)
    bundle = bundle.copy()
    tweet = tweet.copy()
    bundle["level"] = "bundle"
    tweet["level"] = "tweet"

    required = {"mode", "variant", "topic", "stance", "level"}
    for name, df in [("bundle", bundle), ("tweet", tweet)]:
        missing = sorted(required - set(df.columns))
        if missing:
            raise ValueError(f"{name} synthetic CSV missing required columns: {missing}")

    stacked = pd.concat(
        [bundle[["mode", "variant", "topic", "stance", "level"]], tweet[["mode", "variant", "topic", "stance", "level"]]],
        ignore_index=True,
    )
    stacked["topic"] = stacked["topic"].astype(str).str.strip()
    stacked = stacked[stacked["topic"].isin(target_topics)].copy()
    stacked["stance_norm"] = stacked["stance"].map(normalize_stance)
    stacked = stacked[stacked["stance_norm"] != ""].copy()
    if stacked.empty:
        raise RuntimeError("No synthetic rows matched PEW topics after stance normalization.")

    rows: List[Dict[str, object]] = []
    group_cols = ["mode", "variant", "level", "topic"]
    for key, sub in stacked.groupby(group_cols, dropna=False):
        mode, variant, level, topic = key
        counts = sub["stance_norm"].value_counts()
        positive_n = float(counts.get("support", 0))
        negative_n = float(counts.get("reject", 0))
        neutral_n = float(counts.get("neutral", 0))
        valid_n = positive_n + negative_n + neutral_n
        if valid_n <= 0:
            continue

        pos_pct = (positive_n / valid_n) * 100.0
        neg_pct = (negative_n / valid_n) * 100.0
        neu_pct = (neutral_n / valid_n) * 100.0
        net = pos_pct - neg_pct
        rows.append(
            {
                "mode": str(mode),
                "variant": str(variant),
                "level": str(level),
                "issue_topic": str(topic),
                "synthetic_valid_n": int(valid_n),
                "synthetic_positive_n": int(positive_n),
                "synthetic_negative_n": int(negative_n),
                "synthetic_neutral_n": int(neutral_n),
                "synthetic_positive_pct_valid": round(pos_pct, 6),
                "synthetic_negative_pct_valid": round(neg_pct, 6),
                "synthetic_neutral_pct_valid": round(neu_pct, 6),
                "synthetic_net_positive_minus_negative": round(net, 6),
            }
        )

    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError("Synthetic topic distribution is empty.")
    out = out.sort_values(["mode", "variant", "level", "issue_topic"], kind="mergesort").reset_index(drop=True)
    return out


def main() -> None:
    args = parse_args()
    pew_path = Path(args.pew_topic_summary)
    syn_bundle_path = Path(args.synthetic_bundle)
    syn_tweet_path = Path(args.synthetic_tweet)
    output_dir = Path(args.output_dir)

    for p in [pew_path, syn_bundle_path, syn_tweet_path]:
        if not p.exists():
            raise FileNotFoundError(f"Required input file not found: {p}")

    outputs = {
        "synthetic_topic_summary": output_dir / "synthetic_topic_summary.csv",
        "pew_synthetic_topic_comparison": output_dir / "pew_synthetic_topic_comparison.csv",
        "pew_synthetic_alignment_metrics": output_dir / "pew_synthetic_alignment_metrics.csv",
        "manifest": output_dir / "rq3_alignment_manifest.json",
    }
    if not args.overwrite:
        for path in outputs.values():
            if path.exists():
                raise FileExistsError(f"Output already exists: {path}. Use --overwrite.")

    pew = pd.read_csv(pew_path)
    required_pew = {
        "issue_topic",
        "weighted_positive_pct_valid",
        "weighted_negative_pct_valid",
        "weighted_net_positive_minus_negative",
    }
    missing_pew_cols = sorted(required_pew - set(pew.columns))
    if missing_pew_cols:
        raise ValueError(f"PEW topic summary missing columns: {missing_pew_cols}")

    pew = pew.copy()
    pew["issue_topic"] = pew["issue_topic"].astype(str).str.strip()
    pew = pew[pew["issue_topic"] != ""].copy()
    if pew.empty:
        raise RuntimeError("PEW topic summary has no topics.")

    target_topics = sorted(pew["issue_topic"].unique().tolist())
    synthetic = build_synthetic_topic_distribution(syn_bundle_path, syn_tweet_path, target_topics)

    comparison = synthetic.merge(
        pew[
            [
                "issue_topic",
                "questions_count",
                "waves_count",
                "weighted_positive_pct_valid",
                "weighted_negative_pct_valid",
                "weighted_neutral_pct_valid",
                "weighted_net_positive_minus_negative",
            ]
        ],
        on="issue_topic",
        how="left",
    )
    comparison["delta_positive_pct"] = (
        comparison["synthetic_positive_pct_valid"] - comparison["weighted_positive_pct_valid"]
    ).round(6)
    comparison["delta_negative_pct"] = (
        comparison["synthetic_negative_pct_valid"] - comparison["weighted_negative_pct_valid"]
    ).round(6)
    comparison["delta_net"] = (
        comparison["synthetic_net_positive_minus_negative"]
        - comparison["weighted_net_positive_minus_negative"]
    ).round(6)
    comparison = comparison.sort_values(
        ["mode", "variant", "level", "issue_topic"], kind="mergesort"
    ).reset_index(drop=True)

    metric_rows: List[Dict[str, object]] = []
    cfg_cols = ["mode", "variant", "level"]
    for key, sub in comparison.groupby(cfg_cols, dropna=False):
        mode, variant, level = key
        sub = sub.sort_values("issue_topic", kind="mergesort")
        topics = sub["issue_topic"].tolist()

        pew_pos = sub["weighted_positive_pct_valid"].astype(float).tolist()
        syn_pos = sub["synthetic_positive_pct_valid"].astype(float).tolist()
        pew_neg = sub["weighted_negative_pct_valid"].astype(float).tolist()
        syn_neg = sub["synthetic_negative_pct_valid"].astype(float).tolist()
        pew_net = sub["weighted_net_positive_minus_negative"].astype(float).tolist()
        syn_net = sub["synthetic_net_positive_minus_negative"].astype(float).tolist()

        pos_rank = rank_agreement_stats(topics, pew_pos, syn_pos)
        net_rank = rank_agreement_stats(topics, pew_net, syn_net)

        metric_rows.append(
            {
                "mode": str(mode),
                "variant": str(variant),
                "level": str(level),
                "n_topics": len(topics),
                "pearson_r_positive_pct": safe_pearson(pew_pos, syn_pos),
                "pearson_r_negative_pct": safe_pearson(pew_neg, syn_neg),
                "pearson_r_net": safe_pearson(pew_net, syn_net),
                "spearman_r_positive_pct": safe_spearman(pew_pos, syn_pos),
                "spearman_r_net": safe_spearman(pew_net, syn_net),
                "mae_positive_pct": mean_abs_error(pew_pos, syn_pos),
                "mae_negative_pct": mean_abs_error(pew_neg, syn_neg),
                "mae_net": mean_abs_error(pew_net, syn_net),
                "positive_mean_abs_rank_diff": pos_rank["mean_abs_rank_diff"],
                "positive_top1_topic_match": pos_rank["top1_topic_match"],
                "positive_exact_rank_order_match": pos_rank["exact_rank_order_match"],
                "net_mean_abs_rank_diff": net_rank["mean_abs_rank_diff"],
                "net_top1_topic_match": net_rank["top1_topic_match"],
                "net_exact_rank_order_match": net_rank["exact_rank_order_match"],
            }
        )

    metrics = pd.DataFrame(metric_rows).sort_values(
        ["mode", "variant", "level"], kind="mergesort"
    ).reset_index(drop=True)

    def round_cols(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
        out = df.copy()
        for col in cols:
            if col in out.columns:
                out[col] = out[col].apply(
                    lambda x: round(float(x), 6) if pd.notna(x) and x != "" else x
                )
        return out

    metrics = round_cols(
        metrics,
        [
            "pearson_r_positive_pct",
            "pearson_r_negative_pct",
            "pearson_r_net",
            "spearman_r_positive_pct",
            "spearman_r_net",
            "mae_positive_pct",
            "mae_negative_pct",
            "mae_net",
            "positive_mean_abs_rank_diff",
            "net_mean_abs_rank_diff",
        ],
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    synthetic.to_csv(outputs["synthetic_topic_summary"], index=False, encoding="utf-8")
    comparison.to_csv(outputs["pew_synthetic_topic_comparison"], index=False, encoding="utf-8")
    metrics.to_csv(outputs["pew_synthetic_alignment_metrics"], index=False, encoding="utf-8")

    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {
            "pew_topic_summary": str(pew_path),
            "synthetic_bundle": str(syn_bundle_path),
            "synthetic_tweet": str(syn_tweet_path),
        },
        "target_topics": target_topics,
        "synthetic_rows": int(len(synthetic)),
        "comparison_rows": int(len(comparison)),
        "config_count": int(len(metrics)),
        "outputs": {k: str(v) for k, v in outputs.items()},
    }
    outputs["manifest"].write_text(json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    print(f"Target topics: {len(target_topics)}")
    print(f"Synthetic topic rows: {len(synthetic)}")
    print(f"Comparison rows: {len(comparison)}")
    print(f"Configurations scored: {len(metrics)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
