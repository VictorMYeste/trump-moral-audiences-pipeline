#!/usr/bin/env python3
"""Validate RQ1 label result tables and export key-pattern checks."""

# Simple explanation of this script (step by step):
# 1) Load generated label tables and stance-distribution tables.
# 2) Run numeric and structural consistency checks.
# 3) Verify weighted means and stance-score reconstruction.
# 4) Extract top/bottom topic contrasts by metric/mode/level.
# 5) Save a compact validation bundle (CSV + JSON + Markdown).

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


DEFAULT_RESULTS_DIR = "docs/private/RQ1/RQ1_all_label_results"
DEFAULT_ANALYSIS_DIR = "docs/private/RQ1/RQ1_all_label_analysis"
EXPECTED_METRICS = ["stance_score", "agreement", "legitimacy", "offensiveness", "endorsement"]
EXPECTED_MODES = ["iw", "mft"]
EXPECTED_LEVELS = ["tweet", "bundle"]
EXPECTED_VARIANTS = ["neigh", "topk"]
RANGES = {
    "stance_score": (-1.0, 1.0),
    "agreement": (1.0, 5.0),
    "legitimacy": (1.0, 5.0),
    "offensiveness": (1.0, 5.0),
    "endorsement": (1.0, 5.0),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run consistency checks and key-pattern extraction for RQ1 label results."
    )
    parser.add_argument(
        "--results-dir",
        default=DEFAULT_RESULTS_DIR,
        help="Folder produced by scripts/build_rq1_label_plots.py",
    )
    parser.add_argument(
        "--analysis-dir",
        default=DEFAULT_ANALYSIS_DIR,
        help="Folder produced by scripts/analyze_rq1_labels.py",
    )
    parser.add_argument(
        "--outdir",
        default="validation",
        help="Subfolder name inside results-dir for validation artifacts",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite validation outputs if they already exist",
    )
    return parser.parse_args()


def ensure_output_dir(path: Path, overwrite: bool) -> None:
    if path.exists() and not overwrite and any(path.iterdir()):
        raise FileExistsError(f"Output directory already has files: {path}. Use --overwrite.")
    path.mkdir(parents=True, exist_ok=True)


def bool_status(ok: bool) -> str:
    return "pass" if ok else "fail"


def metric_sign(value: float, eps: float = 1e-9) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def main() -> None:
    args = parse_args()
    results_dir = Path(args.results_dir)
    analysis_dir = Path(args.analysis_dir)
    outdir = results_dir / args.outdir
    ensure_output_dir(outdir, args.overwrite)

    by_path = results_dir / "tables" / "rq1_label_table_by_topic_polarity.csv"
    overall_path = results_dir / "tables" / "rq1_label_table_overall.csv"
    rank_path = results_dir / "tables" / "rq1_label_topic_contrast_ranking.csv"
    stance_dist_path = analysis_dir / "rq1_stance_distribution.csv"
    ingest_path = analysis_dir / "rq1_ingest_report.csv"

    required = [by_path, overall_path, rank_path, stance_dist_path, ingest_path]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(f"Missing required inputs: {missing}")

    by = pd.read_csv(by_path)
    overall = pd.read_csv(overall_path)
    rank = pd.read_csv(rank_path)
    stance_dist = pd.read_csv(stance_dist_path)
    ingest = pd.read_csv(ingest_path)

    checks: List[Dict[str, object]] = []

    # Shape/schema checks
    checks.append(
        {
            "check_name": "expected_variants",
            "status": bool_status(sorted(set(by["variant"].unique())) == sorted(EXPECTED_VARIANTS)),
            "detail": f"variants={sorted(set(by['variant'].unique()))}",
        }
    )
    checks.append(
        {
            "check_name": "expected_modes",
            "status": bool_status(sorted(set(by["mode"].unique())) == sorted(EXPECTED_MODES)),
            "detail": f"modes={sorted(set(by['mode'].unique()))}",
        }
    )
    checks.append(
        {
            "check_name": "expected_levels",
            "status": bool_status(sorted(set(by["level"].unique())) == sorted(EXPECTED_LEVELS)),
            "detail": f"levels={sorted(set(by['level'].unique()))}",
        }
    )
    checks.append(
        {
            "check_name": "expected_metrics",
            "status": bool_status(sorted(set(by["metric"].unique())) == sorted(EXPECTED_METRICS)),
            "detail": f"metrics={sorted(set(by['metric'].unique()))}",
        }
    )

    # Range checks
    for metric, (lo, hi) in RANGES.items():
        sub = by[by["metric"] == metric][["positive", "neutral", "negative"]].stack()
        observed_min = float(sub.min())
        observed_max = float(sub.max())
        ok = observed_min >= lo - 1e-9 and observed_max <= hi + 1e-9
        checks.append(
            {
                "check_name": f"range_{metric}",
                "status": bool_status(ok),
                "detail": (
                    f"min={observed_min:.6f}, max={observed_max:.6f}, expected=[{lo:.1f},{hi:.1f}]"
                ),
            }
        )

    # Weighted-mean consistency
    weighted_failures = 0
    max_weighted_diff = 0.0
    for _, row in by.iterrows():
        mask = (
            (overall["mode"] == row["mode"])
            & (overall["variant"] == row["variant"])
            & (overall["topic"] == row["topic"])
            & (overall["level"] == row["level"])
            & (overall["metric"] == row["metric"])
        )
        if not mask.any():
            weighted_failures += 1
            continue
        overall_row = overall[mask].iloc[0]
        numerator = (
            row["positive"] * row["n_positive"]
            + row["neutral"] * row["n_neutral"]
            + row["negative"] * row["n_negative"]
        )
        denominator = row["n_positive"] + row["n_neutral"] + row["n_negative"]
        weighted_mean = numerator / denominator
        diff = abs(weighted_mean - overall_row["mean"])
        max_weighted_diff = max(max_weighted_diff, float(diff))
        if diff > 1e-6:
            weighted_failures += 1

    checks.append(
        {
            "check_name": "weighted_mean_consistency",
            "status": bool_status(weighted_failures == 0),
            "detail": f"failures={weighted_failures}, max_abs_diff={max_weighted_diff:.12f}",
        }
    )

    # Stance reconstruction from distribution
    map_values = {"reject": -1.0, "neutral": 0.0, "support": 1.0}
    stance_dist = stance_dist.copy()
    stance_dist["score"] = stance_dist["stance"].map(map_values)
    stance_dist["weighted"] = stance_dist["score"] * stance_dist["pct"]
    agg = (
        stance_dist.groupby(
            ["mode", "variant", "topic", "level", "persona_polarity"], as_index=False
        )["weighted"]
        .sum()
        .rename(columns={"weighted": "reconstructed"})
    )
    pivot = agg.pivot_table(
        index=["mode", "variant", "topic", "level"],
        columns="persona_polarity",
        values="reconstructed",
    ).reset_index()
    stance_rows = by[by["metric"] == "stance_score"].merge(
        pivot, on=["mode", "variant", "topic", "level"], how="left", suffixes=("_obs", "_recon")
    )

    max_stance_diff = 0.0
    for polarity in ["positive", "neutral", "negative"]:
        observed_col = f"{polarity}_obs"
        recon_col = f"{polarity}_recon"
        if observed_col not in stance_rows.columns or recon_col not in stance_rows.columns:
            continue
        diffs = (stance_rows[observed_col] - stance_rows[recon_col]).abs()
        local_max = float(diffs.max()) if len(diffs) else 0.0
        max_stance_diff = max(max_stance_diff, local_max)

    checks.append(
        {
            "check_name": "stance_distribution_consistency",
            "status": bool_status(max_stance_diff <= 1e-6 + 1e-12),
            "detail": f"max_abs_diff={max_stance_diff:.12f}",
        }
    )

    # Parse-error overview
    parse_error_df = ingest[ingest["records_parse_error_skipped"] > 0].copy()
    total_records = int(ingest["records_total"].sum())
    total_parse_errors = int(ingest["records_parse_error_skipped"].sum())
    parse_error_rate = (total_parse_errors / total_records) if total_records else 0.0
    checks.append(
        {
            "check_name": "parse_error_rate",
            "status": bool_status(parse_error_rate <= 0.01),
            "detail": (
                f"parse_errors={total_parse_errors}, records={total_records}, "
                f"rate={parse_error_rate:.6f}"
            ),
        }
    )

    # Key pattern extraction (top and bottom contrast per mode/level/metric)
    pattern_rows: List[Dict[str, object]] = []
    for mode in sorted(rank["mode"].unique()):
        mode_rank = rank[rank["mode"] == mode]
        for variant in sorted(mode_rank["variant"].unique()):
            for level in sorted(rank["level"].unique()):
                for metric in EXPECTED_METRICS:
                    subset = rank[
                        (rank["mode"] == mode)
                        & (rank["variant"] == variant)
                        & (rank["level"] == level)
                        & (rank["metric"] == metric)
                    ].sort_values("positive_minus_negative", ascending=False, kind="mergesort")
                    if subset.empty:
                        continue
                    top = subset.iloc[0]
                    bottom = subset.iloc[-1]
                    pattern_rows.append(
                        {
                            "mode": mode,
                            "variant": variant,
                            "level": level,
                            "metric": metric,
                            "extreme": "top",
                            "topic": top["topic"],
                            "positive_minus_negative": float(top["positive_minus_negative"]),
                        }
                    )
                    pattern_rows.append(
                        {
                            "mode": mode,
                            "variant": variant,
                            "level": level,
                            "metric": metric,
                            "extreme": "bottom",
                            "topic": bottom["topic"],
                            "positive_minus_negative": float(bottom["positive_minus_negative"]),
                        }
                    )
    pattern_df = pd.DataFrame(pattern_rows)

    # Directional consistency (tweet vs bundle sign of pos-neg contrast)
    pivot = rank.pivot_table(
        index=["mode", "variant", "metric", "topic"],
        columns="level",
        values="positive_minus_negative",
        aggfunc="first",
    ).reset_index()
    if "tweet" not in pivot.columns:
        pivot["tweet"] = pd.NA
    if "bundle" not in pivot.columns:
        pivot["bundle"] = pd.NA
    pivot["tweet_sign"] = pivot["tweet"].apply(lambda x: metric_sign(float(x)) if pd.notna(x) else None)
    pivot["bundle_sign"] = pivot["bundle"].apply(lambda x: metric_sign(float(x)) if pd.notna(x) else None)
    pivot["same_sign"] = pivot["tweet_sign"] == pivot["bundle_sign"]

    consistency_rate = float(pivot["same_sign"].mean()) if not pivot.empty else 0.0
    checks.append(
        {
            "check_name": "tweet_bundle_direction_consistency",
            "status": bool_status(consistency_rate >= 0.8),
            "detail": f"same_sign_rate={consistency_rate:.6f}",
        }
    )

    checks_df = pd.DataFrame(checks)
    checks_path = outdir / "rq1_validation_checks.csv"
    checks_df.to_csv(checks_path, index=False, encoding="utf-8")

    patterns_path = outdir / "rq1_key_patterns.csv"
    pattern_df.to_csv(patterns_path, index=False, encoding="utf-8")

    direction_path = outdir / "rq1_direction_consistency.csv"
    pivot.to_csv(direction_path, index=False, encoding="utf-8")

    parse_errors_path = outdir / "rq1_parse_error_breakdown.csv"
    parse_error_df.to_csv(parse_errors_path, index=False, encoding="utf-8")

    summary = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "inputs": {
            "by_topic_polarity": str(by_path),
            "overall": str(overall_path),
            "contrast_ranking": str(rank_path),
            "stance_distribution": str(stance_dist_path),
            "ingest_report": str(ingest_path),
        },
        "totals": {
            "rows_by_topic_polarity": int(len(by)),
            "rows_overall": int(len(overall)),
            "rows_ranking": int(len(rank)),
            "parse_errors": total_parse_errors,
            "total_records": total_records,
            "parse_error_rate": parse_error_rate,
        },
        "check_status_counts": checks_df["status"].value_counts().to_dict(),
        "outputs": {
            "checks_csv": str(checks_path),
            "patterns_csv": str(patterns_path),
            "direction_csv": str(direction_path),
            "parse_errors_csv": str(parse_errors_path),
            "summary_json": str(outdir / "rq1_validation_summary.json"),
            "report_md": str(outdir / "rq1_validation_report.md"),
        },
    }
    summary_path = outdir / "rq1_validation_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    pass_count = int((checks_df["status"] == "pass").sum())
    fail_count = int((checks_df["status"] == "fail").sum())

    lines = [
        "# RQ1 Validation Report",
        "",
        f"- Generated: `{summary['created_at_utc']}`",
        f"- Checks: `{pass_count}` pass, `{fail_count}` fail",
        f"- Parse errors skipped: `{total_parse_errors}/{total_records}` (`{parse_error_rate:.4%}`)",
        "",
        "## Check Results",
        "",
        "| check_name | status | detail |",
        "|---|---|---|",
    ]
    for _, row in checks_df.iterrows():
        lines.append(f"| {row['check_name']} | {row['status']} | {row['detail']} |")

    lines += [
        "",
        "## Parse Error Breakdown (rows with parse errors)",
        "",
        "| mode | topic | variant | records_total | records_parse_error_skipped |",
        "|---|---|---:|---:|---:|",
    ]
    for _, row in parse_error_df.iterrows():
        lines.append(
            "| "
            f"{row['mode']} | {row['topic']} | {row['variant']} | "
            f"{int(row['records_total'])} | {int(row['records_parse_error_skipped'])} |"
        )

    lines += [
        "",
        "## Key Contrast Extremes",
        "",
        "| mode | variant | level | metric | extreme | topic | positive_minus_negative |",
        "|---|---|---|---|---|---|---:|",
    ]
    for _, row in pattern_df.iterrows():
        lines.append(
            "| "
            f"{row['mode']} | {row['variant']} | {row['level']} | {row['metric']} | {row['extreme']} | "
            f"{row['topic']} | {row['positive_minus_negative']:.6f} |"
        )

    report_path = outdir / "rq1_validation_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Checks: {pass_count} pass / {fail_count} fail")
    print(f"Validation output: {outdir}")


if __name__ == "__main__":
    main()
