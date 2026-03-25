#!/usr/bin/env python3
"""Build final RQ4 topic list plus PEW/posts subsets from overlap topics."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


PEW_DEFAULT = "data/interim/pew/pew_rq4_inventory.csv"
POSTS_DEFAULT = "data/interim/preprocessing/posts_prompt_ready.csv"
OUTDIR_DEFAULT = "data/interim/rq4"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build final RQ4 topics and write PEW/posts subsets restricted to overlap topics."
        )
    )
    parser.add_argument("--pew", default=PEW_DEFAULT, help=f"PEW RQ4 CSV (default: {PEW_DEFAULT})")
    parser.add_argument(
        "--posts",
        default=POSTS_DEFAULT,
        help=f"Prompt-ready posts CSV (default: {POSTS_DEFAULT})",
    )
    parser.add_argument(
        "--outdir",
        default=OUTDIR_DEFAULT,
        help=f"Output directory (default: {OUTDIR_DEFAULT})",
    )
    parser.add_argument(
        "--min-pew-per-topic",
        type=int,
        default=1,
        help="Minimum included PEW rows required per topic (default: 1)",
    )
    parser.add_argument(
        "--min-posts-per-topic",
        type=int,
        default=1,
        help="Minimum prompt-ready posts required per topic (default: 1)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output files if they already exist",
    )
    return parser.parse_args()


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalized(value: str) -> str:
    return (value or "").strip()


def main() -> None:
    args = parse_args()
    pew_path = Path(args.pew)
    posts_path = Path(args.posts)
    outdir = Path(args.outdir)

    if not pew_path.exists():
        raise FileNotFoundError(f"PEW file not found: {pew_path}")
    if not posts_path.exists():
        raise FileNotFoundError(f"Posts file not found: {posts_path}")

    topics_path = outdir / "rq4_topics_final.csv"
    pew_subset_path = outdir / "rq4_pew_subset.csv"
    posts_subset_path = outdir / "rq4_posts_subset.csv"

    if not args.overwrite:
        for target in [topics_path, pew_subset_path, posts_subset_path]:
            if target.exists():
                raise FileExistsError(
                    f"Output already exists: {target}. Use --overwrite to replace it."
                )

    pew_fields, pew_rows = read_csv(pew_path)
    posts_fields, posts_rows = read_csv(posts_path)

    required_pew_cols = {"issue_topic", "include_for_rq4"}
    if not required_pew_cols.issubset(set(pew_fields)):
        raise ValueError("PEW CSV must include columns: issue_topic, include_for_rq4")
    if "topic" not in set(posts_fields):
        raise ValueError("Posts CSV must include column: topic")

    pew_included = [
        row
        for row in pew_rows
        if normalized(row.get("include_for_rq4", "")).lower() == "yes"
        and normalized(row.get("issue_topic", ""))
    ]
    pew_topic_counts = Counter(normalized(row.get("issue_topic", "")) for row in pew_included)
    posts_topic_counts = Counter(
        normalized(row.get("topic", "")) for row in posts_rows if normalized(row.get("topic", ""))
    )

    overlap_topics = sorted(set(pew_topic_counts) & set(posts_topic_counts))
    final_topics = [
        topic
        for topic in overlap_topics
        if pew_topic_counts[topic] >= args.min_pew_per_topic
        and posts_topic_counts[topic] >= args.min_posts_per_topic
    ]
    final_topic_set = set(final_topics)

    topic_rows = [
        {
            "topic": topic,
            "pew_rows": str(pew_topic_counts[topic]),
            "post_rows": str(posts_topic_counts[topic]),
        }
        for topic in final_topics
    ]
    pew_subset = [row for row in pew_included if normalized(row.get("issue_topic", "")) in final_topic_set]
    posts_subset = [row for row in posts_rows if normalized(row.get("topic", "")) in final_topic_set]

    write_csv(topics_path, ["topic", "pew_rows", "post_rows"], topic_rows)
    write_csv(pew_subset_path, pew_fields, pew_subset)
    write_csv(posts_subset_path, posts_fields, posts_subset)

    print(f"PEW file: {pew_path}")
    print(f"Posts file: {posts_path}")
    print(f"min_pew_per_topic: {args.min_pew_per_topic}")
    print(f"min_posts_per_topic: {args.min_posts_per_topic}")
    print(f"Included PEW rows before overlap filtering: {len(pew_included)}")
    print(f"Topics in included PEW rows: {len(pew_topic_counts)}")
    print(f"Topics in prompt-ready posts: {len(posts_topic_counts)}")
    print(f"Overlap topics before thresholds: {len(overlap_topics)}")
    print(f"Final topics after thresholds: {len(final_topics)}")
    print(f"PEW subset rows written: {len(pew_subset)}")
    print(f"Posts subset rows written: {len(posts_subset)}")
    print(f"Topics output: {topics_path}")
    print(f"PEW subset output: {pew_subset_path}")
    print(f"Posts subset output: {posts_subset_path}")


if __name__ == "__main__":
    main()
