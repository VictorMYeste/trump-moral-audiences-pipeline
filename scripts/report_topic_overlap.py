#!/usr/bin/env python3
"""Report topic overlap between PEW RQ4 inventory and prompt-ready posts."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set


PEW_DEFAULT = "data/interim/pew/pew_rq4_inventory.csv"
POSTS_DEFAULT = "data/interim/preprocessing/posts_prompt_ready.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Print topic coverage overlap between PEW RQ4 inventory and prompt-ready "
            "posts."
        )
    )
    parser.add_argument("--pew", default=PEW_DEFAULT, help=f"PEW RQ4 CSV (default: {PEW_DEFAULT})")
    parser.add_argument(
        "--posts",
        default=POSTS_DEFAULT,
        help=f"Prompt-ready posts CSV (default: {POSTS_DEFAULT})",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Max rows to show in summary tables (default: 20)",
    )
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader)


def normalize_topic(value: str) -> str:
    return (value or "").strip()


def print_table(
    title: str,
    rows: List[Dict[str, str]],
    columns: List[str],
    top_n: int,
) -> None:
    print(title)
    if not rows:
        print("  (none)")
        return
    rows = rows[:top_n]
    widths = {col: max(len(col), *(len(str(r.get(col, ""))) for r in rows)) for col in columns}
    header = "  " + " | ".join(col.ljust(widths[col]) for col in columns)
    sep = "  " + "-+-".join("-" * widths[col] for col in columns)
    print(header)
    print(sep)
    for row in rows:
        line = "  " + " | ".join(str(row.get(col, "")).ljust(widths[col]) for col in columns)
        print(line)


def main() -> None:
    args = parse_args()
    pew_path = Path(args.pew)
    posts_path = Path(args.posts)

    if not pew_path.exists():
        raise FileNotFoundError(f"PEW file not found: {pew_path}")
    if not posts_path.exists():
        raise FileNotFoundError(f"Posts file not found: {posts_path}")

    pew_rows = read_csv(pew_path)
    posts_rows = read_csv(posts_path)

    required_pew = {"issue_topic", "include_for_rq4", "exclude_code"}
    if not required_pew.issubset(pew_rows[0].keys() if pew_rows else set()):
        raise ValueError(
            "PEW CSV must include columns: issue_topic, include_for_rq4, exclude_code"
        )
    if "topic" not in (posts_rows[0].keys() if posts_rows else set()):
        raise ValueError("Posts CSV must include column: topic")

    pew_included = [row for row in pew_rows if row.get("include_for_rq4", "").strip().lower() == "yes"]
    pew_excluded = [row for row in pew_rows if row.get("include_for_rq4", "").strip().lower() != "yes"]

    pew_topic_included_counts = Counter(
        normalize_topic(row.get("issue_topic", "")) for row in pew_included if normalize_topic(row.get("issue_topic", ""))
    )
    pew_topic_any_counts = Counter(
        normalize_topic(row.get("issue_topic", "")) for row in pew_rows if normalize_topic(row.get("issue_topic", ""))
    )
    posts_topic_counts = Counter(
        normalize_topic(row.get("topic", "")) for row in posts_rows if normalize_topic(row.get("topic", ""))
    )

    included_topics: Set[str] = set(pew_topic_included_counts)
    posts_topics: Set[str] = set(posts_topic_counts)
    overlap_topics = sorted(included_topics & posts_topics)
    pew_only_topics = sorted(included_topics - posts_topics)
    posts_only_topics = sorted(posts_topics - included_topics)

    exclude_code_counts = Counter(
        normalize_topic(row.get("exclude_code", "")) for row in pew_excluded if normalize_topic(row.get("exclude_code", ""))
    )

    print(f"PEW file: {pew_path}")
    print(f"Posts file: {posts_path}")
    print(f"PEW rows: {len(pew_rows)}")
    print(f"PEW included rows (include_for_rq4=yes): {len(pew_included)}")
    print(f"PEW excluded rows: {len(pew_excluded)}")
    print(f"Prompt-ready posts rows: {len(posts_rows)}")
    print("")

    print(f"Included PEW topics: {len(included_topics)}")
    print(f"Prompt-ready post topics: {len(posts_topics)}")
    print(f"Topic overlap (included PEW ∩ posts): {len(overlap_topics)}")
    print("")

    print("Overlap topics:")
    if overlap_topics:
        for topic in overlap_topics:
            print(f"  {topic}: pew_included={pew_topic_included_counts[topic]}, posts={posts_topic_counts[topic]}")
    else:
        print("  (none)")
    print("")

    print("Included PEW topics with no post coverage:")
    if pew_only_topics:
        for topic in pew_only_topics:
            print(f"  {topic}: pew_included={pew_topic_included_counts[topic]}, posts=0")
    else:
        print("  (none)")
    print("")

    print("Post topics with no included PEW coverage:")
    if posts_only_topics:
        for topic in posts_only_topics:
            print(f"  {topic}: posts={posts_topic_counts[topic]}")
    else:
        print("  (none)")
    print("")

    top_any_pew_rows = [
        {"issue_topic": topic, "count": count}
        for topic, count in pew_topic_any_counts.most_common(args.top_n)
    ]
    print_table(
        title=f"Top PEW issue_topic counts (all rows, top {args.top_n}):",
        rows=top_any_pew_rows,
        columns=["issue_topic", "count"],
        top_n=args.top_n,
    )
    print("")

    top_exclude_rows = [
        {"exclude_code": code, "count": count}
        for code, count in exclude_code_counts.most_common(args.top_n)
    ]
    print_table(
        title=f"Top PEW exclude_code counts (top {args.top_n}):",
        rows=top_exclude_rows,
        columns=["exclude_code", "count"],
        top_n=args.top_n,
    )
    print("")

    top_posts_rows = [
        {"topic": topic, "count": count}
        for topic, count in posts_topic_counts.most_common(args.top_n)
    ]
    print_table(
        title=f"Top prompt-ready post topic counts (top {args.top_n}):",
        rows=top_posts_rows,
        columns=["topic", "count"],
        top_n=args.top_n,
    )


if __name__ == "__main__":
    main()
