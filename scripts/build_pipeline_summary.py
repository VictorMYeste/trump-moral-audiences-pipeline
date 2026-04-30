#!/usr/bin/env python3
"""Build a compact, reproducible pipeline summary artifact."""

# Simple explanation of this script (step by step):
# 1) Read the main output files from the pipeline (PEW, RQ3, and posts).
# 2) Compute key counts (included/excluded, topics, overlaps, etc.).
# 3) Summarize results by wave and by processing stage.
# 4) Generate two reports: one readable (`.md`) and one structured (`.json`).

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


PARTIAL_GLOB_DEFAULT = "data/pew_datasets/W*/pew_question_inventory_partial.csv"
MERGED_DEFAULT = "data/interim/pew/pew_question_inventory.csv"
RQ3_DEFAULT = "data/interim/pew/pew_rq3_inventory.csv"
POSTS_VALIDATED_DEFAULT = "data/interim/preprocessing/posts_topic_validated.csv"
POSTS_PROMPT_DEFAULT = "data/interim/preprocessing/posts_prompt_ready.csv"
FINAL_TOPICS_DEFAULT = "data/interim/rq3/rq3_topics_final.csv"
OUTPUT_MD_DEFAULT = "reports/pipeline_summary.md"
OUTPUT_JSON_DEFAULT = "reports/pipeline_summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Markdown and JSON summary from pipeline outputs."
    )
    parser.add_argument("--partial-glob", default=PARTIAL_GLOB_DEFAULT)
    parser.add_argument("--merged", default=MERGED_DEFAULT)
    parser.add_argument("--rq3", default=RQ3_DEFAULT)
    parser.add_argument("--posts-validated", default=POSTS_VALIDATED_DEFAULT)
    parser.add_argument("--posts-prompt", default=POSTS_PROMPT_DEFAULT)
    parser.add_argument("--final-topics", default=FINAL_TOPICS_DEFAULT)
    parser.add_argument("--output-md", default=OUTPUT_MD_DEFAULT)
    parser.add_argument("--output-json", default=OUTPUT_JSON_DEFAULT)
    return parser.parse_args()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader)


def read_optional_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return []
        return list(reader)


def markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()

    partial_paths = [p for p in sorted(Path(".").glob(args.partial_glob)) if p.is_file()]
    merged_rows = read_csv_rows(Path(args.merged))
    rq3_rows = read_csv_rows(Path(args.rq3))
    posts_validated_rows = read_csv_rows(Path(args.posts_validated))
    posts_prompt_rows = read_csv_rows(Path(args.posts_prompt))
    final_topic_rows = read_optional_csv_rows(Path(args.final_topics))

    partial_by_wave: List[Dict[str, str]] = []
    for path in partial_paths:
        rows = read_csv_rows(path)
        wave_folder = path.parent.name
        partial_by_wave.append(
            {
                "wave_folder": wave_folder,
                "path": str(path),
                "rows": str(len(rows)),
            }
        )

    include_counts = Counter((r.get("include_for_rq3") or "").strip() for r in rq3_rows)
    exclude_counts = Counter((r.get("exclude_code") or "").strip() for r in rq3_rows if (r.get("exclude_code") or "").strip())

    included_topic_counts = Counter(
        (r.get("issue_topic") or "").strip()
        for r in rq3_rows
        if (r.get("include_for_rq3") or "").strip().lower() == "yes" and (r.get("issue_topic") or "").strip()
    )

    post_topic_counts = Counter((r.get("topic") or "").strip() for r in posts_prompt_rows if (r.get("topic") or "").strip())
    moderation_counts = Counter((r.get("moderation_status") or "").strip() for r in posts_validated_rows if (r.get("moderation_status") or "").strip())

    overlap_topics = sorted(set(included_topic_counts) & set(post_topic_counts))

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "wave_partial_files": len(partial_paths),
            "wave_partial_rows_total": sum(int(r["rows"]) for r in partial_by_wave),
            "merged_inventory_rows": len(merged_rows),
            "rq3_inventory_rows": len(rq3_rows),
            "rq3_include_yes": include_counts.get("yes", 0),
            "rq3_include_no": include_counts.get("no", 0),
            "posts_validated_rows": len(posts_validated_rows),
            "posts_prompt_ready_rows": len(posts_prompt_rows),
            "final_topics_rows": len(final_topic_rows),
            "overlap_topic_count": len(overlap_topics),
        },
        "wave_partial_rows": partial_by_wave,
        "rq3_exclude_counts": dict(exclude_counts),
        "rq3_included_topic_counts": dict(included_topic_counts),
        "prompt_topic_counts": dict(post_topic_counts),
        "moderation_status_counts": dict(moderation_counts),
        "overlap_topics": overlap_topics,
        "final_topics": final_topic_rows,
    }

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    lines: List[str] = []
    lines.append("# Pipeline Summary")
    lines.append("")
    lines.append(f"Generated (UTC): `{summary['generated_utc']}`")
    lines.append("")

    lines.append("## Headline Counts")
    lines.append("")
    headline_rows = [[k, str(v)] for k, v in summary["counts"].items()]
    lines.append(markdown_table(["metric", "value"], headline_rows))
    lines.append("")

    lines.append("## Wave Partial Rows")
    lines.append("")
    if partial_by_wave:
        lines.append(
            markdown_table(
                ["wave_folder", "rows", "path"],
                [[r["wave_folder"], r["rows"], r["path"]] for r in partial_by_wave],
            )
        )
    else:
        lines.append("No partial inventory files found.")
    lines.append("")

    lines.append("## RQ3 Exclude Codes")
    lines.append("")
    if exclude_counts:
        rows = [[k, str(v)] for k, v in exclude_counts.most_common()]
        lines.append(markdown_table(["exclude_code", "count"], rows))
    else:
        lines.append("No exclude codes present.")
    lines.append("")

    lines.append("## Included PEW Topic Counts")
    lines.append("")
    if included_topic_counts:
        rows = [[k, str(v)] for k, v in sorted(included_topic_counts.items())]
        lines.append(markdown_table(["issue_topic", "count"], rows))
    else:
        lines.append("No included PEW topics.")
    lines.append("")

    lines.append("## Prompt-Ready Topic Counts")
    lines.append("")
    if post_topic_counts:
        rows = [[k, str(v)] for k, v in post_topic_counts.most_common()]
        lines.append(markdown_table(["topic", "count"], rows))
    else:
        lines.append("No prompt-ready topic counts available.")
    lines.append("")

    lines.append("## Moderation Status Counts")
    lines.append("")
    if moderation_counts:
        rows = [[k, str(v)] for k, v in sorted(moderation_counts.items())]
        lines.append(markdown_table(["moderation_status", "count"], rows))
    else:
        lines.append("No moderation status counts available.")
    lines.append("")

    lines.append("## Overlap Topics")
    lines.append("")
    if overlap_topics:
        rows = [[topic, str(included_topic_counts.get(topic, 0)), str(post_topic_counts.get(topic, 0))] for topic in overlap_topics]
        lines.append(markdown_table(["topic", "pew_included_rows", "prompt_ready_rows"], rows))
    else:
        lines.append("No overlap topics.")
    lines.append("")

    lines.append("## Final Topics File")
    lines.append("")
    if final_topic_rows:
        rows = [[r.get("topic", ""), r.get("pew_rows", ""), r.get("post_rows", "")] for r in final_topic_rows]
        lines.append(markdown_table(["topic", "pew_rows", "post_rows"], rows))
    else:
        lines.append("Final topics file is empty or missing.")
    lines.append("")

    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- JSON summary: `{out_json}`")

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(f"Summary written: {out_md}")
    print(f"Summary JSON: {out_json}")


if __name__ == "__main__":
    main()
