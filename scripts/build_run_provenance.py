#!/usr/bin/env python3
"""Build a compact provenance artifact for one pipeline run."""

# Simple explanation of this script (step by step):
# 1) Record when the run happened.
# 2) Record the key input file paths used by the pipeline.
# 3) Detect wave folders from the configured wave glob.
# 4) Write one machine-readable JSON file and one human-readable Markdown file in reports/.

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


RAW_POSTS_DEFAULT = "data/raw/trump_archive_me2bert_filtered_2021.csv"
WAVE_GLOB_DEFAULT = "data/pew_datasets/W*"
MANIFEST_DEFAULT = "data/reference/pew/waves_manifest.csv"
FILTER_SPEC_DEFAULT = "data/reference/methods/filter_spec.json"
TOPIC_SPEC_DEFAULT = "data/reference/methods/topic_keywords.json"
OUTPUT_MD_DEFAULT = "reports/run_provenance.md"
OUTPUT_JSON_DEFAULT = "reports/run_provenance.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a compact run-level provenance artifact."
    )
    parser.add_argument("--raw-posts", default=RAW_POSTS_DEFAULT)
    parser.add_argument("--wave-glob", default=WAVE_GLOB_DEFAULT)
    parser.add_argument("--manifest", default=MANIFEST_DEFAULT)
    parser.add_argument("--filter-spec", default=FILTER_SPEC_DEFAULT)
    parser.add_argument("--topic-spec", default=TOPIC_SPEC_DEFAULT)
    parser.add_argument("--output-md", default=OUTPUT_MD_DEFAULT)
    parser.add_argument("--output-json", default=OUTPUT_JSON_DEFAULT)
    return parser.parse_args()


def markdown_table(headers: List[str], rows: List[List[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def describe_path(path_str: str) -> Dict[str, str]:
    path = Path(path_str)
    return {
        "path": str(path),
        "name": path.name,
        "exists": "yes" if path.exists() else "no",
    }


def main() -> None:
    args = parse_args()

    wave_paths = [p for p in sorted(Path(".").glob(args.wave_glob)) if p.is_dir()]
    generated_utc = datetime.now(timezone.utc).isoformat()

    inputs = {
        "raw_posts": describe_path(args.raw_posts),
        "manifest": describe_path(args.manifest),
        "filter_spec": describe_path(args.filter_spec),
        "topic_spec": describe_path(args.topic_spec),
    }

    wave_folders = [
        {
            "folder_name": p.name,
            "path": str(p),
        }
        for p in wave_paths
    ]

    payload = {
        "generated_utc": generated_utc,
        "wave_glob": args.wave_glob,
        "inputs": inputs,
        "wave_folder_count": len(wave_folders),
        "wave_folders": wave_folders,
    }

    out_json = Path(args.output_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    lines: List[str] = []
    lines.append("# Run Provenance")
    lines.append("")
    lines.append(f"Generated (UTC): `{generated_utc}`")
    lines.append(f"Wave glob: `{args.wave_glob}`")
    lines.append("")
    lines.append("## Input Files")
    lines.append("")
    lines.append(
        markdown_table(
            ["input_name", "file_name", "path", "exists"],
            [
                [name, meta["name"], meta["path"], meta["exists"]]
                for name, meta in inputs.items()
            ],
        )
    )
    lines.append("")
    lines.append("## Detected Wave Folders")
    lines.append("")
    if wave_folders:
        lines.append(
            markdown_table(
                ["wave_folder", "path"],
                [[item["folder_name"], item["path"]] for item in wave_folders],
            )
        )
    else:
        lines.append("No wave folders detected.")
    lines.append("")
    lines.append("## Artifacts")
    lines.append("")
    lines.append(f"- JSON provenance: `{out_json}`")

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    print(f"Run provenance written: {out_md}")
    print(f"Run provenance JSON: {out_json}")


if __name__ == "__main__":
    main()
