#!/usr/bin/env python3
"""Copy and sanitize publishable report artifacts from reports/ to docs/artifacts/."""

# Simple explanation of this script (step by step):
# 1) Select the report files that are publishable for the paper appendix.
# 2) Read each file from reports/ and sanitize local path information.
# 3) Copy sanitized outputs to docs/artifacts/ with stable paths.
# 4) Write an artifact manifest that lists what was exported and what was missing.

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


SOURCE_ROOT_DEFAULT = "reports"
OUTDIR_DEFAULT = "docs/artifacts"

PUBLISHABLE_REL_PATHS = [
    "methods/filter_table.csv",
    "methods/topic_patterns.csv",
    "methods/anonymization_rules.csv",
    "methods/pew_selection_rules.csv",
    "methods/decision_audit.md",
    "pipeline_summary.md",
    "pipeline_summary.json",
    "run_provenance.md",
    "run_provenance.json",
]

UNIX_USERS_RE = re.compile(r"/Users/([^/\s`\"']+)")
UNIX_HOME_RE = re.compile(r"/home/([^/\s`\"']+)")
WIN_USERS_RE = re.compile(r"([A-Za-z]:\\Users\\)([^\\/\s`\"']+)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export sanitized publishable reports from reports/ to docs/artifacts/."
    )
    parser.add_argument("--source-root", default=SOURCE_ROOT_DEFAULT)
    parser.add_argument("--outdir", default=OUTDIR_DEFAULT)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Allow overwriting output files if they already exist.",
    )
    return parser.parse_args()


def sanitize_text(text: str, repo_root: Path) -> str:
    repo_root_str = str(repo_root)
    output = text.replace(repo_root_str, ".")
    output = UNIX_USERS_RE.sub("/Users/[REDACTED]", output)
    output = UNIX_HOME_RE.sub("/home/[REDACTED]", output)
    output = WIN_USERS_RE.sub(r"\1[REDACTED]", output)
    return output


def write_manifest(outdir: Path, payload: Dict[str, object]) -> None:
    manifest_path = outdir / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def write_index_md(outdir: Path, payload: Dict[str, object]) -> None:
    exported = payload.get("exported", [])
    missing = payload.get("missing", [])
    if not isinstance(exported, list):
        exported = []
    if not isinstance(missing, list):
        missing = []

    lines: List[str] = []
    lines.append("# Publishable Artifacts")
    lines.append("")
    lines.append(f"Generated (UTC): `{payload.get('generated_utc', '')}`")
    lines.append(f"Source root: `{payload.get('source_root', '')}`")
    lines.append("")
    lines.append("## Exported")
    lines.append("")
    if exported:
        for item in exported:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- `{item.get('source', '')}` -> `{item.get('destination', '')}`"
            )
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Missing")
    lines.append("")
    if missing:
        for rel in missing:
            lines.append(f"- `{rel}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "- These files are sanitized copies intended for public repository transparency."
    )
    lines.append("- Raw run artifacts remain under `reports/` and stay gitignored.")

    (outdir / "README.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    source_root = Path(args.source_root)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parent.parent
    generated_utc = datetime.now(timezone.utc).isoformat()

    exported: List[Dict[str, str]] = []
    missing: List[str] = []

    for rel in PUBLISHABLE_REL_PATHS:
        src = source_root / rel
        dst = outdir / rel
        if not src.exists():
            missing.append(rel)
            continue
        if dst.exists() and not args.overwrite:
            raise FileExistsError(
                f"Output already exists: {dst}. Use --overwrite to replace."
            )

        text = src.read_text(encoding="utf-8")
        sanitized = sanitize_text(text, repo_root)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(sanitized, encoding="utf-8")

        exported.append({"source": str(src), "destination": str(dst)})

    payload: Dict[str, object] = {
        "generated_utc": generated_utc,
        "source_root": str(source_root),
        "outdir": str(outdir),
        "exported_count": len(exported),
        "missing_count": len(missing),
        "exported": exported,
        "missing": missing,
    }

    write_manifest(outdir, payload)
    write_index_md(outdir, payload)

    print(f"Exported publishable artifacts: {len(exported)}")
    print(f"Missing source artifacts: {len(missing)}")
    print(f"Output directory: {outdir}")
    print(f"Manifest: {outdir / 'artifact_manifest.json'}")


if __name__ == "__main__":
    main()
