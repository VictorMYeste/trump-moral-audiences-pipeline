#!/usr/bin/env bash
set -euo pipefail

# Simple explanation of this script (step by step):
# 1) Refresh the wave manifest (optional) and validate inputs before processing.
# 2) Build PEW partial files per wave and then merge them.
# 3) Select PEW rows valid for RQ4.
# 4) Preprocess posts and compute topic overlap.
# 5) Generate final PEW/post subsets, run summary, and export methods appendix artifacts.

usage() {
  cat <<'EOF'
Run the full RQ4 preprocessing pipeline end-to-end.

Usage:
  scripts/run_full_pipeline.sh [options]

Options:
  --python BIN                 Python executable to use (default: python3)
  --wave-glob GLOB             Wave folder glob (default: data/pew_datasets/W*)
  --manifest PATH              Wave manifest CSV (default: data/reference/pew/waves_manifest.csv)
  --no-refresh-manifest        Do not auto-rebuild manifest from wave folders
  --manual-review-csv PATH     Optional manual overrides for preprocess_posts.py
  --min-pew-per-topic N        Threshold for build_rq4_final_subsets.py (default: 1)
  --min-posts-per-topic N      Threshold for build_rq4_final_subsets.py (default: 1)
  --skip-preflight             Skip wave input preflight validation
  --skip-summary               Skip pipeline summary artifact generation
  --skip-methods               Skip methods appendix artifact generation
  --no-overwrite               Do not pass --overwrite to scripts that support it
  -h, --help                   Show this help

Examples:
  scripts/run_full_pipeline.sh
  scripts/run_full_pipeline.sh --manifest data/reference/pew/waves_manifest.csv
  scripts/run_full_pipeline.sh --no-refresh-manifest
  scripts/run_full_pipeline.sh --manual-review-csv data/manual/overrides.csv
  scripts/run_full_pipeline.sh --min-pew-per-topic 2 --min-posts-per-topic 50
EOF
}

PYTHON_BIN="python3"
WAVE_GLOB="data/pew_datasets/W*"
MANIFEST_PATH="data/reference/pew/waves_manifest.csv"
MANUAL_REVIEW_CSV=""
MIN_PEW_PER_TOPIC=1
MIN_POSTS_PER_TOPIC=1
REFRESH_MANIFEST=1
SKIP_PREFLIGHT=0
SKIP_SUMMARY=0
SKIP_METHODS=0
OVERWRITE=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --wave-glob)
      WAVE_GLOB="$2"
      shift 2
      ;;
    --manifest)
      MANIFEST_PATH="$2"
      shift 2
      ;;
    --no-refresh-manifest)
      REFRESH_MANIFEST=0
      shift
      ;;
    --manual-review-csv)
      MANUAL_REVIEW_CSV="$2"
      shift 2
      ;;
    --min-pew-per-topic)
      MIN_PEW_PER_TOPIC="$2"
      shift 2
      ;;
    --min-posts-per-topic)
      MIN_POSTS_PER_TOPIC="$2"
      shift 2
      ;;
    --skip-preflight)
      SKIP_PREFLIGHT=1
      shift
      ;;
    --skip-summary)
      SKIP_SUMMARY=1
      shift
      ;;
    --skip-methods)
      SKIP_METHODS=1
      shift
      ;;
    --no-overwrite)
      OVERWRITE=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$REPO_ROOT"

if [[ $REFRESH_MANIFEST -eq 1 ]]; then
  echo "[prep] Rebuilding wave manifest from folders..."
  "$PYTHON_BIN" scripts/build_waves_manifest.py --wave-glob "$WAVE_GLOB" --output "$MANIFEST_PATH"
fi

if [[ $SKIP_PREFLIGHT -eq 0 ]]; then
  echo "[0/9] Running preflight validation..."
  PREFLIGHT_CMD=( "$PYTHON_BIN" scripts/validate_pew_wave_inputs.py --wave-glob "$WAVE_GLOB" )
  if [[ -n "$MANIFEST_PATH" ]]; then
    PREFLIGHT_CMD+=( --manifest "$MANIFEST_PATH" )
  fi
  "${PREFLIGHT_CMD[@]}"
fi

echo "[1/9] Building per-wave PEW partial inventories..."
shopt -s nullglob
wave_dirs=( $WAVE_GLOB )
if [[ ${#wave_dirs[@]} -eq 0 ]]; then
  echo "No wave folders matched glob: $WAVE_GLOB" >&2
  exit 1
fi
for d in "${wave_dirs[@]}"; do
  if [[ -d "$d" ]]; then
    echo "  - $d"
    if [[ $OVERWRITE -eq 1 ]]; then
      "$PYTHON_BIN" scripts/build_pew_inventory.py --wave-folder "$d" --overwrite
    else
      "$PYTHON_BIN" scripts/build_pew_inventory.py --wave-folder "$d"
    fi
  fi
done
shopt -u nullglob

echo "[2/9] Merging partial inventories..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/merge_pew_inventories.py --overwrite
else
  "$PYTHON_BIN" scripts/merge_pew_inventories.py
fi

echo "[3/9] Selecting PEW rows for RQ4..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/select_pew_for_rq4.py --overwrite
else
  "$PYTHON_BIN" scripts/select_pew_for_rq4.py
fi

echo "[4/9] Preprocessing posts..."
POSTS_CMD=( "$PYTHON_BIN" scripts/preprocess_posts.py )
if [[ -n "$MANUAL_REVIEW_CSV" ]]; then
  POSTS_CMD+=( --manual-review-csv "$MANUAL_REVIEW_CSV" )
fi
"${POSTS_CMD[@]}"

echo "[5/9] Reporting topic overlap..."
"$PYTHON_BIN" scripts/report_topic_overlap.py

echo "[6/9] Building final RQ4 topic list and subsets..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/build_rq4_final_subsets.py \
    --min-pew-per-topic "$MIN_PEW_PER_TOPIC" \
    --min-posts-per-topic "$MIN_POSTS_PER_TOPIC" \
    --overwrite
else
  "$PYTHON_BIN" scripts/build_rq4_final_subsets.py \
    --min-pew-per-topic "$MIN_PEW_PER_TOPIC" \
    --min-posts-per-topic "$MIN_POSTS_PER_TOPIC"
fi

if [[ $SKIP_SUMMARY -eq 0 ]]; then
  echo "[7/9] Building pipeline summary artifacts..."
  "$PYTHON_BIN" scripts/build_pipeline_summary.py
fi

if [[ $SKIP_METHODS -eq 0 ]]; then
  echo "[8/9] Exporting methods appendix artifacts..."
  "$PYTHON_BIN" scripts/export_methods_appendix.py
fi

echo "Pipeline completed."
