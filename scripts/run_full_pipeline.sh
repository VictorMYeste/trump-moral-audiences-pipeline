#!/usr/bin/env bash
set -euo pipefail

# Simple explanation of this script (step by step):
# 1) Refresh the wave manifest (optional) and validate inputs before processing.
# 2) Validate shared topic keyword registry used across PEW and post filters.
# 3) Build PEW partial files per wave and then merge them.
# 4) Select PEW rows valid for RQ3.
# 5) Preprocess posts and compute topic overlap.
# 6) Generate final PEW/post subsets.
# 7) Build RQ3-ready PEW weighted distributions and PEW-vs-synthetic alignment metrics.
# 8) Write provenance, summary, methods, and publishable artifacts.

usage() {
  cat <<'EOF'
Run the full preprocessing pipeline end-to-end (RQ3 subsets + RQ3 alignment artifacts).

Usage:
  scripts/run_full_pipeline.sh [options]

Options:
  --python BIN                 Python executable to use (default: python3)
  --raw-posts PATH             Raw post CSV path. Repeat to combine multiple raw files
  --wave-glob GLOB             Wave folder glob (default: data/pew_datasets/W*)
  --manifest PATH              Wave manifest CSV (default: data/reference/pew/waves_manifest.csv)
  --no-refresh-manifest        Do not auto-rebuild manifest from wave folders
  --manual-review-csv PATH     Optional manual overrides for preprocess_posts.py
  --min-pew-per-topic N        Threshold for build_rq3_final_subsets.py (default: 1)
  --min-posts-per-topic N      Threshold for build_rq3_final_subsets.py (default: 1)
  --skip-preflight             Skip wave input preflight validation
  --skip-summary               Skip pipeline summary artifact generation
  --skip-methods               Skip methods appendix artifact generation
  --skip-publishable           Skip export of sanitized publishable artifacts
  --no-log                     Disable automatic tee logging to logs/
  --log-file PATH              Custom log file path (default: logs/run_full_pipeline_YYYYmmdd_HHMMSS.log)
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
RAW_POSTS_DEFAULT=(
  "data/raw/trump_archive_me2bert_filtered_2009_2021.csv"
  "data/raw/trump_manual_me2bert_filtered_2022_2024.csv"
)
RAW_POSTS=( "${RAW_POSTS_DEFAULT[@]}" )
RAW_POSTS_EXPLICIT=0
WAVE_GLOB="data/pew_datasets/W*"
MANIFEST_PATH="data/reference/pew/waves_manifest.csv"
MANUAL_REVIEW_CSV=""
MIN_PEW_PER_TOPIC=1
MIN_POSTS_PER_TOPIC=1
REFRESH_MANIFEST=1
SKIP_PREFLIGHT=0
SKIP_SUMMARY=0
SKIP_METHODS=0
SKIP_PUBLISHABLE=0
AUTO_LOG=1
LOG_FILE=""
OVERWRITE=1
ORIGINAL_ARGC=$#
if (( ORIGINAL_ARGC > 0 )); then
  ORIGINAL_ARGS=( "$@" )
fi

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
    --raw-posts)
      if [[ $RAW_POSTS_EXPLICIT -eq 0 ]]; then
        RAW_POSTS=()
        RAW_POSTS_EXPLICIT=1
      fi
      RAW_POSTS+=( "$2" )
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
    --skip-publishable)
      SKIP_PUBLISHABLE=1
      shift
      ;;
    --no-log)
      AUTO_LOG=0
      shift
      ;;
    --log-file)
      LOG_FILE="$2"
      shift 2
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

if [[ "${PIPELINE_LOG_ACTIVE:-0}" != "1" && $AUTO_LOG -eq 1 ]]; then
  if [[ -z "$LOG_FILE" ]]; then
    ts="$(date +%Y%m%d_%H%M%S)"
    LOG_FILE="logs/run_full_pipeline_${ts}.log"
  fi
  mkdir -p "$(dirname "$LOG_FILE")"
  echo "[log] Writing run log to: $LOG_FILE"
  if (( ORIGINAL_ARGC > 0 )); then
    PIPELINE_LOG_ACTIVE=1 "$0" "${ORIGINAL_ARGS[@]}" 2>&1 | tee "$LOG_FILE"
  else
    PIPELINE_LOG_ACTIVE=1 "$0" 2>&1 | tee "$LOG_FILE"
  fi
  exit "${PIPESTATUS[0]}"
fi

ACTIVE_RAW_POSTS=()
if [[ $RAW_POSTS_EXPLICIT -eq 1 ]]; then
  ACTIVE_RAW_POSTS=( "${RAW_POSTS[@]}" )
else
  for raw_path in "${RAW_POSTS[@]}"; do
    if [[ -f "$raw_path" ]]; then
      ACTIVE_RAW_POSTS+=( "$raw_path" )
    fi
  done
fi

if [[ $REFRESH_MANIFEST -eq 1 ]]; then
  echo "[prep] Rebuilding wave manifest from folders..."
  "$PYTHON_BIN" scripts/build_waves_manifest.py --wave-glob "$WAVE_GLOB" --output "$MANIFEST_PATH"
fi

if [[ $SKIP_PREFLIGHT -eq 0 ]]; then
  echo "[0/14] Running preflight validation..."
  PREFLIGHT_CMD=( "$PYTHON_BIN" scripts/validate_pew_wave_inputs.py --wave-glob "$WAVE_GLOB" )
  if [[ -n "$MANIFEST_PATH" ]]; then
    PREFLIGHT_CMD+=( --manifest "$MANIFEST_PATH" )
  fi
  "${PREFLIGHT_CMD[@]}"
fi

echo "[1/14] Validating shared topic registry..."
"$PYTHON_BIN" scripts/validate_topic_rules.py

echo "[2/14] Building per-wave PEW partial inventories..."
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

echo "[3/14] Merging partial inventories..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/merge_pew_inventories.py --overwrite
else
  "$PYTHON_BIN" scripts/merge_pew_inventories.py
fi

echo "[4/14] Selecting PEW rows for RQ3..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/select_pew_for_rq3.py --overwrite
else
  "$PYTHON_BIN" scripts/select_pew_for_rq3.py
fi

echo "[5/14] Preprocessing posts..."
POSTS_CMD=( "$PYTHON_BIN" scripts/preprocess_posts.py )
if [[ ${#ACTIVE_RAW_POSTS[@]} -gt 0 ]]; then
  for raw_path in "${ACTIVE_RAW_POSTS[@]}"; do
    POSTS_CMD+=( --input "$raw_path" )
  done
fi
if [[ -n "$MANUAL_REVIEW_CSV" ]]; then
  POSTS_CMD+=( --manual-review-csv "$MANUAL_REVIEW_CSV" )
fi
"${POSTS_CMD[@]}"

echo "[6/14] Reporting topic overlap..."
"$PYTHON_BIN" scripts/report_topic_overlap.py

echo "[7/14] Building final RQ3 topic list and subsets..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/build_rq3_final_subsets.py \
    --min-pew-per-topic "$MIN_PEW_PER_TOPIC" \
    --min-posts-per-topic "$MIN_POSTS_PER_TOPIC" \
    --overwrite
else
  "$PYTHON_BIN" scripts/build_rq3_final_subsets.py \
    --min-pew-per-topic "$MIN_PEW_PER_TOPIC" \
    --min-posts-per-topic "$MIN_POSTS_PER_TOPIC"
fi

echo "[8/14] Extracting weighted PEW distributions for RQ3..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/extract_pew_weighted_distributions.py --overwrite
else
  "$PYTHON_BIN" scripts/extract_pew_weighted_distributions.py
fi

echo "[9/14] Computing PEW-vs-synthetic RQ3 alignment metrics..."
if [[ $OVERWRITE -eq 1 ]]; then
  "$PYTHON_BIN" scripts/compute_rq3_alignment.py --overwrite
else
  "$PYTHON_BIN" scripts/compute_rq3_alignment.py
fi

echo "[10/14] Writing run provenance artifact..."
PROVENANCE_CMD=( "$PYTHON_BIN" scripts/build_run_provenance.py --wave-glob "$WAVE_GLOB" --manifest "$MANIFEST_PATH" )
if [[ ${#ACTIVE_RAW_POSTS[@]} -gt 0 ]]; then
  for raw_path in "${ACTIVE_RAW_POSTS[@]}"; do
    PROVENANCE_CMD+=( --raw-posts "$raw_path" )
  done
fi
"${PROVENANCE_CMD[@]}"

if [[ $SKIP_SUMMARY -eq 0 ]]; then
  echo "[11/14] Building pipeline summary artifacts..."
  "$PYTHON_BIN" scripts/build_pipeline_summary.py
fi

if [[ $SKIP_METHODS -eq 0 ]]; then
  echo "[12/14] Exporting methods appendix artifacts..."
  METHODS_CMD=( "$PYTHON_BIN" scripts/export_methods_appendix.py )
  if [[ ${#ACTIVE_RAW_POSTS[@]} -gt 0 ]]; then
    for raw_path in "${ACTIVE_RAW_POSTS[@]}"; do
      METHODS_CMD+=( --raw "$raw_path" )
    done
  fi
  "${METHODS_CMD[@]}"
fi

if [[ $SKIP_PUBLISHABLE -eq 0 ]]; then
  echo "[13/14] Exporting publishable sanitized artifacts..."
  PUBLISHABLE_CMD=( "$PYTHON_BIN" scripts/export_publishable_reports.py )
  if [[ $OVERWRITE -eq 1 ]]; then
    PUBLISHABLE_CMD+=( --overwrite )
  fi
  "${PUBLISHABLE_CMD[@]}"
fi

echo "Pipeline completed."
