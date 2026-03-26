#!/usr/bin/env python3
"""Validate canonical topic-keyword registry and print a compact summary."""

# Simple explanation of this script (step by step):
# 1) Load the shared topic keyword registry JSON.
# 2) Validate required fields and regex compilation.
# 3) Print the topic list and where each topic is applied (posts, PEW, or both).
# 4) Exit with non-zero status if the registry is invalid.

from __future__ import annotations

import argparse
from pathlib import Path

import topic_rules as tr


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the canonical topic keyword registry."
    )
    parser.add_argument(
        "--spec",
        default=str(tr.default_topic_spec_path()),
        help="Topic registry JSON path",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    spec_path = Path(args.spec)
    spec = tr.load_topic_spec(spec_path)

    metadata = spec.get("metadata", {})
    topics = spec.get("topics", [])
    version = ""
    if isinstance(metadata, dict):
        version = str(metadata.get("spec_version", "")).strip()

    print(f"Spec: {spec_path}")
    if version:
        print(f"Spec version: {version}")
    print(f"Topic count: {len(topics) if isinstance(topics, list) else 0}")
    print("Topics:")

    if isinstance(topics, list):
        for item in topics:
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "")).strip()
            applies = item.get("applies_to", [])
            applies_text = "|".join(str(v) for v in applies) if isinstance(applies, list) else ""
            print(f"  - {topic}: applies_to={applies_text}")

    print("Validation: OK")


if __name__ == "__main__":
    main()
