# Paper Trump Moral Audiences

Project workspace for building:
1. A clean, anonymized, topic-labeled Trump post dataset for prompting.
2. A PEW question inventory aligned to ATP waves for real-vs-synthetic comparison.

Core design docs:
- `docs/proposal.md`
- `docs/preprocessing_protocol.md`
- `docs/topic_pew_alignment.md`

## Repository Layout

- `data/raw/trump_archive_me2bert_filtered_2021.csv`: source Trump posts dataset (local, not committed).
- `data/raw/trump_archive_me2bert_filtered_2024.csv`: planned extension dataset (local, not committed; not yet added).
- `data/interim/preprocessing/`: staged post preprocessing outputs.
- `data/pew_datasets/W*/`: one folder per ATP wave (`.sav`, `readme`, optional PDFs, partial inventory).
- `data/reference/pew/waves_manifest.csv`: manifest of wave folders to validate before running.
- `data/reference/examples/raw_input_sample.csv`: synthetic example of expected raw input schema.
- `scripts/preprocess_posts.py`: post cleaning, topic labeling, anonymization, prompt-ready filtering.
- `scripts/build_waves_manifest.py`: auto-build wave manifest by scanning wave folders.
- `scripts/validate_pew_wave_inputs.py`: preflight validation of wave folders (`readme` and `.sav` checks).
- `scripts/build_pew_inventory.py`: generate one wave-level PEW inventory partial.
- `scripts/merge_pew_inventories.py`: merge all wave partials into one master inventory.
- `scripts/select_pew_for_rq4.py`: create a minimal, deterministic PEW selection table for RQ4.
- `scripts/report_topic_overlap.py`: print PEW vs prompt-ready topic overlap and coverage counts.
- `scripts/build_rq4_final_subsets.py`: build final overlap topic list and subset both PEW rows and posts.
- `scripts/build_pipeline_summary.py`: generate run-level Markdown/JSON summary artifacts.
- `scripts/run_full_pipeline.sh`: run the full end-to-end sequence in one command.
- `data/interim/pew/pew_question_inventory.csv`: merged PEW inventory (generated).
- `data/interim/pew/pew_rq4_inventory.csv`: RQ4 deterministic selection table (generated).

## External Data Sources

Post corpus sources:
- Kaggle dataset (`headsortails/trump-twitter-archive`):
  - URL: <https://www.kaggle.com/datasets/headsortails/trump-twitter-archive>
  - URL (plain): https://www.kaggle.com/datasets/headsortails/trump-twitter-archive
- The Trump Archive:
  - URL: <https://www.thetrumparchive.com/>
  - URL (plain): https://www.thetrumparchive.com/

Project windows:
1. Current phase dataset (up to 2021):
   - local file: `data/raw/trump_archive_me2bert_filtered_2021.csv`
   - source: Kaggle `headsortails/trump-twitter-archive`
   - post date window used in current preprocessing protocol: `2009-05-12` to `2021-01-08`
2. Planned extension dataset (2021-2024):
   - local file: `data/raw/trump_archive_me2bert_filtered_2024.csv`
   - source: The Trump Archive (`https://www.thetrumparchive.com/`)
   - target window for extension analyses: `2021-01-09` to `2024-12-31`

When publishing, cite both data sources used for each window and include access/download dates.

## Data Publishing Policy

Public repository policy:
- Do not commit raw source data.
- Do not commit downloaded PEW wave files.
- Do not commit generated interim outputs derived from raw data.

Git-ignore scope:
- `data/raw/`
- `data/pew_datasets/`
- `data/interim/`
- `reports/`
- `docs/private/`

Publishable data artifacts:
- `data/reference/` (templates and synthetic examples only)

## Data Availability

This repository publishes code, documentation, and synthetic/reference artifacts only.

Not publicly distributed in this repository:
- `data/raw/` source post dataset
- `data/pew_datasets/` downloaded ATP wave files (`.sav`, PDFs, readmes)
- `data/interim/` generated outputs derived from restricted/source data

Publicly distributed in this repository:
- preprocessing and selection scripts in `scripts/`
- reproducibility documentation in `docs/`
- templates and synthetic examples in `data/reference/`

How to reproduce results with your own data access:
1. Download source data and prepare local raw CSV files under `data/raw/` using the expected schema:
   - from Kaggle (`headsortails/trump-twitter-archive`) for `trump_archive_me2bert_filtered_2021.csv`
   - from The Trump Archive (`https://www.thetrumparchive.com/`) for `trump_archive_me2bert_filtered_2024.csv`
2. Obtain PEW ATP wave files and place each wave under `data/pew_datasets/W*/`.
3. Run `scripts/run_full_pipeline.sh`.
4. Use outputs in `data/interim/` (local) and run reports in `reports/` (local).

Access and redistribution of PEW ATP files and raw post data must follow their original licensing/terms.

## Raw Input Format

Expected raw CSV header (17 columns):
- `id,text,isRetweet,isDeleted,device,favorites,retweets,date,isFlagged,CH,FC,LB,AS,PD,moral_max,dominant_moral_dimension,is_morally_relevant`

Minimum fields required by `preprocess_posts.py`:
- `id`, `text`, `isRetweet`, `isDeleted`, `date`, `isFlagged`, `dominant_moral_dimension`, `is_morally_relevant`

Date format:
- `YYYY-MM-DD HH:MM:SS`

Boolean formats accepted by parser:
- `true/false`, `t/f`, `1/0`, `yes/no` (case-insensitive)

Synthetic sample file:
- `data/reference/examples/raw_input_sample.csv`

Detailed field contract:
- `docs/preprocessing_protocol.md` (Section `2.1 Expected Raw CSV Schema`)

## Requirements

- Python 3.9+.
- `strings` command available in shell (used to inspect `.sav` labels).
- `pypdf` installed in the same Python environment used to run scripts.

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Quick check:

```bash
python3 -c "import pypdf; print(pypdf.__version__)"
```

## End-to-End Workflow

1. Run `build_waves_manifest.py` to auto-build `waves_manifest.csv` from downloaded wave folders.
2. Run `validate_pew_wave_inputs.py` to catch missing/invalid wave folders before extraction.
3. Run `build_pew_inventory.py` for each wave to create `pew_question_inventory_partial.csv`.
4. Run `merge_pew_inventories.py` to produce `data/interim/pew/pew_question_inventory.csv`.
5. Run `select_pew_for_rq4.py` to auto-select rows compatible with current RQ4 constraints.
6. Run `preprocess_posts.py` to generate prompt-ready post bundles.
7. Run `report_topic_overlap.py` to inspect PEW-vs-post topic coverage.
8. Run `build_rq4_final_subsets.py` to produce one final topic list and both final subsets.
9. Run `build_pipeline_summary.py` to produce auditable run summaries in `reports/`.

## Script: preprocess_posts.py

Purpose:
- Applies protocol rules to source posts.
- Adds derived metadata (role, moderation status, cleaned text, topics).
- Anonymizes text and excludes rows not suitable for first prompt-ready pool.
- Keeps moderation statuses for analysis in a separate output.

Basic run:

```bash
python3 scripts/preprocess_posts.py
```

Arguments:
- `--input` (default `data/raw/trump_archive_me2bert_filtered_2021.csv`)
- `--outdir` (default `data/interim/preprocessing`)
- `--manual-review-csv` optional overrides file with columns:
  - `id` (required)
  - `topic`
  - `topic_confidence`
  - `review_flag`
  - `exclude_reason_add`

Manual override run:

```bash
python3 scripts/preprocess_posts.py \
  --manual-review-csv manual_review_overrides.csv
```

Outputs in `data/interim/preprocessing/`:
1. `posts_clean.csv`
2. `posts_topic_labeled.csv`
3. `posts_topic_validated.csv`
4. `posts_prompt_ready.csv`
5. `posts_moderation_analysis.csv`

## Script: build_pew_inventory.py

Purpose:
- Builds one wave-level partial inventory from ATP wave files.
- Uses `readme + .sav` extraction for variable names/question text.
- Uses ATP codebook PDF (via `pypdf`) to detect `F_` profile variables and improve cleanup.
- Uses a single minimal output schema (manual-alignment columns are not created).

Basic run for one wave:

```bash
python3 scripts/build_pew_inventory.py \
  --wave-folder data/pew_datasets/W55_Oct19 \
  --overwrite
```

Arguments:
- `--wave-folder` required wave directory.
- `--codebook-pdf` default `data/pew_datasets/Codebook-and-instructions-for-working-with-ATP-data.pdf`.
- `--output` optional custom output path.
- `--trump-only` default enabled. Keep only Trump-related variables/questions.
- `--no-trump-only` disable Trump-only filtering.
- `--include-weights` include `WEIGHT_*` variables (excluded by default).
- `--include-cross-wave` include non-current-wave variables (excluded by default).
- `--overwrite` replace existing output.

Recommended defaults for this project:
- Keep `--trump-only` enabled (default).
- Keep `--include-weights` disabled (default) because weights are not analysis questions.
- Keep `--include-cross-wave` disabled (default) to avoid pulling non-wave-specific variables.

Output:
- `<wave-folder>/pew_question_inventory_partial.csv` by default.
- In default mode the file contains only:
  - `inventory_id`
  - `pew_wave`
  - `field_dates`
  - `dataset_file`
  - `variable_name`
  - `question_text_raw`

Batch-run all waves:

```bash
for d in data/pew_datasets/W*; do
  python3 scripts/build_pew_inventory.py --wave-folder "$d" --overwrite
done
```

## Script: validate_pew_wave_inputs.py

Purpose:
- Preflight validation for wave folders before running extraction.
- Checks each wave for required files (`*readme*.txt` and `*.sav`).
- Writes `reports/wave_preflight_report.csv`.

Basic run:

```bash
python3 scripts/validate_pew_wave_inputs.py --strict
```

Arguments:
- `--wave-glob` default `data/pew_datasets/W*`.
- `--manifest` default `data/reference/pew/waves_manifest.csv`.
- `--output` default `reports/wave_preflight_report.csv`.
- `--strict/--no-strict` fail or not on missing required files.

## Script: build_waves_manifest.py

Purpose:
- Auto-build `data/reference/pew/waves_manifest.csv` by scanning wave folders.
- Serves as a wave inventory summary (`readme_count`, `sav_count`, `pdf_count`).

Basic run:

```bash
python3 scripts/build_waves_manifest.py
```

Arguments:
- `--wave-glob` default `data/pew_datasets/W*`.
- `--output` default `data/reference/pew/waves_manifest.csv`.
- `--overwrite/--no-overwrite` replace existing output (default: overwrite).
- `--enabled` default `yes`.

## Script: merge_pew_inventories.py

Purpose:
- Merges all wave-level partial inventories into one master inventory.
- Normalizes all rows to the minimal inventory schema.
- Sorts deterministically by `pew_wave` and `variable_name`.
- Deduplicates by `(pew_wave, variable_name)`.

Basic run:

```bash
python3 scripts/merge_pew_inventories.py --overwrite
```

Arguments:
- `--input-glob` default `data/pew_datasets/W*/pew_question_inventory_partial.csv`.
- `--output` default `data/interim/pew/pew_question_inventory.csv`.
- `--overwrite` replace existing output.

Output:
- `data/interim/pew/pew_question_inventory.csv`

## Script: select_pew_for_rq4.py

Purpose:
- Applies deterministic RQ4 inclusion/exclusion rules.
- Produces a minimal selection table with deterministic include/exclude logic.
- Provides auditability via `exclude_code` and `rule_trace`.

Basic run:

```bash
python3 scripts/select_pew_for_rq4.py --overwrite
```

Arguments:
- `--input` default `data/interim/pew/pew_question_inventory.csv`.
- `--output` default `data/interim/pew/pew_rq4_inventory.csv`.
- `--only-included` write only rows with `include_for_rq4=yes`.
- `--overwrite` replace existing output.

Output columns:
- Preserves input columns as-is.
- Adds:
  - `response_scale_raw`
  - `judgment_family`
  - `issue_topic`
  - `include_for_rq4`
  - `exclude_code`
  - `rule_trace`

Important:
- This selector is intentionally high-precision and conservative.
- Some waves can yield zero included rows if they do not match allowed topics/judgment forms.
- `judgment_family` and `response_scale_raw` are computed for all rows (including excluded rows).
- `issue_topic` is filled only when there is exactly one deterministic topic match; otherwise it remains empty.
- `rule_trace` always records topic diagnostics (`topic_hits:...`) even when a row is excluded.
- Console section `Included topic counts` counts only `include_for_rq4=yes` rows.

## Script: report_topic_overlap.py

Purpose:
- Prints topic coverage overlap between `data/interim/pew/pew_rq4_inventory.csv` and `data/interim/preprocessing/posts_prompt_ready.csv`.
- Shows overlap topics, PEW-only topics, post-only topics, and top counts.

Basic run:

```bash
python3 scripts/report_topic_overlap.py
```

Arguments:
- `--pew` default `data/interim/pew/pew_rq4_inventory.csv`.
- `--posts` default `data/interim/preprocessing/posts_prompt_ready.csv`.
- `--top-n` default `20`.

## Script: build_rq4_final_subsets.py

Purpose:
- Converts overlap analysis into concrete outputs for downstream prompting/analysis.
- Keeps only topics present in both included PEW rows and prompt-ready posts.
- Writes final subsets for both datasets restricted to the same topic set.

Basic run:

```bash
python3 scripts/build_rq4_final_subsets.py --overwrite
```

Arguments:
- `--pew` default `data/interim/pew/pew_rq4_inventory.csv`.
- `--posts` default `data/interim/preprocessing/posts_prompt_ready.csv`.
- `--outdir` default `data/interim/rq4`.
- `--min-pew-per-topic` default `1`.
- `--min-posts-per-topic` default `1`.
- `--overwrite` replace existing outputs.

Outputs in `data/interim/rq4/`:
1. `rq4_topics_final.csv` (`topic`, `pew_rows`, `post_rows`)
2. `rq4_pew_subset.csv` (only included PEW rows in final topics)
3. `rq4_posts_subset.csv` (only prompt-ready posts in final topics)

## Script: build_pipeline_summary.py

Purpose:
- Builds auditable run summaries from generated pipeline artifacts.
- Writes both:
  - `reports/pipeline_summary.md`
  - `reports/pipeline_summary.json`

Basic run:

```bash
python3 scripts/build_pipeline_summary.py
```

## Script: run_full_pipeline.sh

Purpose:
- Runs the full workflow in one command, in the same order as the recommended sequence.

Basic run:

```bash
scripts/run_full_pipeline.sh
```

Useful options:
- `--manifest PATH` wave manifest (default `data/reference/pew/waves_manifest.csv`).
- `--no-refresh-manifest` do not auto-build manifest before preflight.
- `--manual-review-csv PATH` pass overrides into `preprocess_posts.py`.
- `--min-pew-per-topic N` threshold for final topic selection.
- `--min-posts-per-topic N` threshold for final topic selection.
- `--skip-preflight` skip wave preflight validation.
- `--skip-summary` skip summary artifact generation.
- `--no-overwrite` do not pass overwrite flags to scripts that support them.

## Recommended Command Sequence

Single command alternative:

```bash
scripts/run_full_pipeline.sh
```

1. Auto-build wave manifest:

```bash
python3 scripts/build_waves_manifest.py
```

2. Run preflight validation:

```bash
python3 scripts/validate_pew_wave_inputs.py --strict
```

3. Build all wave partials:

```bash
for d in data/pew_datasets/W*; do
  python3 scripts/build_pew_inventory.py --wave-folder "$d" --overwrite
done
```

4. Merge all partials:

```bash
python3 scripts/merge_pew_inventories.py --overwrite
```

5. Build deterministic RQ4 selection table:

```bash
python3 scripts/select_pew_for_rq4.py --overwrite
```

6. Preprocess posts:

```bash
python3 scripts/preprocess_posts.py
```

7. Check topic overlap between PEW and prompt-ready posts:

```bash
python3 scripts/report_topic_overlap.py
```

8. Build final topics plus both final subsets:

```bash
python3 scripts/build_rq4_final_subsets.py --overwrite
```

9. Build summary artifacts:

```bash
python3 scripts/build_pipeline_summary.py
```

10. Optionally rerun post preprocessing with manual overrides:

```bash
python3 scripts/preprocess_posts.py --manual-review-csv manual_review_overrides.csv
```

## Common Issues

- `Preflight failed: at least one wave row is missing required files`:
  - check `reports/wave_preflight_report.csv` for missing `readme` or `.sav` files.
- `Codebook loaded: no (pypdf_unavailable)`:
  - install `pypdf` in the same Python environment used by `python3`.
- `Output already exists ...`:
  - rerun with `--overwrite`.
- `No partial inventory files matched` in merge step:
  - confirm each wave folder has `pew_question_inventory_partial.csv`.
- Manual overrides error:
  - the override CSV must include an `id` column.
