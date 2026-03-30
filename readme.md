# Paper Trump Moral Audiences

Project workspace for building:
1. A clean, anonymized, topic-labeled Trump post dataset for prompting.
2. A PEW question inventory aligned to ATP waves for real-vs-synthetic comparison.

Core design docs:
- `docs/proposal.md`
- `docs/preprocessing_protocol.md`
- `docs/topic_pew_alignment.md`
- `docs/topic_keyword_registry.md`
- `docs/data_dictionary.md`

## Repository Layout

- `data/raw/trump_archive_me2bert_filtered_2021.csv`: source Trump posts dataset (local, not committed).
- `data/raw/trump_archive_me2bert_filtered_2024.csv`: planned extension dataset (local, not committed; not yet added).
- `data/interim/preprocessing/`: staged post preprocessing outputs.
- `data/pew_datasets/W*/`: one folder per ATP wave (`.sav`, `readme`, optional PDFs, partial inventory).
- `data/reference/pew/waves_manifest.csv`: manifest of wave folders to validate before running.
- `data/reference/examples/raw_input_sample.csv`: synthetic example of expected raw input schema.
- `scripts/preprocess_posts.py`: post cleaning, topic labeling, anonymization, prompt-ready filtering.
- `scripts/topic_rules.py`: shared topic-registry loader/validator used by post and PEW selectors.
- `scripts/validate_topic_rules.py`: preflight validation of the shared topic keyword registry.
- `scripts/build_waves_manifest.py`: auto-build wave manifest by scanning wave folders.
- `scripts/validate_pew_wave_inputs.py`: preflight validation of wave folders (`.sav` required, `readme` recommended).
- `scripts/build_pew_inventory.py`: generate one wave-level PEW inventory partial.
- `scripts/merge_pew_inventories.py`: merge all wave partials into one master inventory.
- `scripts/select_pew_for_rq4.py`: create a minimal, deterministic PEW selection table for RQ4.
- `scripts/report_topic_overlap.py`: print PEW vs prompt-ready topic overlap and coverage counts.
- `scripts/build_rq4_final_subsets.py`: build final overlap topic list and subset both PEW rows and posts.
- `scripts/build_run_provenance.py`: write a compact run-level provenance artifact under `reports/`.
- `scripts/build_pipeline_summary.py`: generate run-level Markdown/JSON summary artifacts.
- `scripts/export_methods_appendix.py`: export appendix-ready rules/regex/audit artifacts for methods reporting.
- `scripts/export_publishable_reports.py`: sanitize and copy publishable report artifacts to `docs/artifacts/`.
- `scripts/run_full_pipeline.sh`: run the full end-to-end sequence in one command.
- `data/reference/methods/filter_spec.json`: machine-readable canonical filter/selection rule specification.
- `data/reference/methods/topic_keywords.json`: canonical reusable topic-keyword registry (regex + rationale).
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
- `docs/artifacts/` (sanitized publishable report copies exported from `reports/`)

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
3. Run `validate_topic_rules.py` to validate the shared topic-keyword registry.
4. Run `build_pew_inventory.py` for each wave to create `pew_question_inventory_partial.csv`.
5. Run `merge_pew_inventories.py` to produce `data/interim/pew/pew_question_inventory.csv`.
6. Run `select_pew_for_rq4.py` to auto-select rows compatible with current RQ4 constraints.
7. Run `preprocess_posts.py` to generate prompt-ready post bundles.
8. Run `report_topic_overlap.py` to inspect PEW-vs-post topic coverage.
9. Run `build_rq4_final_subsets.py` to produce one final topic list and both final subsets.
10. Run `build_run_provenance.py` to record run date, input files, and detected wave folders in `reports/`.
11. Run `build_pipeline_summary.py` to produce auditable run summaries in `reports/`.
12. Run `export_methods_appendix.py` to generate appendix-ready rule/pattern/audit artifacts in `reports/methods/`.
13. Run `export_publishable_reports.py --overwrite` to copy sanitized publishable report files into `docs/artifacts/`.

## Script: preprocess_posts.py

Purpose:
- Applies protocol rules to source posts.
- Adds derived metadata (role, moderation status, cleaned text, topics).
- Uses shared topic regexes from `data/reference/methods/topic_keywords.json` via `scripts/topic_rules.py`.
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
- Checks each wave for required `.sav` and recommended `*readme*.txt`.
- Writes `reports/wave_preflight_report.csv`.

Basic run:

```bash
python3 scripts/validate_pew_wave_inputs.py --strict
```

Arguments:
- `--wave-glob` default `data/pew_datasets/W*`.
- `--manifest` default `data/reference/pew/waves_manifest.csv`.
- `--output` default `reports/wave_preflight_report.csv`.
- `--strict/--no-strict` fail or not on missing required `.sav` files (missing readme is warning-only).

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
- Uses the same shared topic regex registry as post preprocessing.

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

Column reference:
- `docs/data_dictionary.md` (includes a full dictionary for `rq4_posts_subset.csv`)

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

## Script: build_run_provenance.py

Purpose:
- Writes a compact provenance record for one pipeline run.
- Captures run date, key input file names/paths, and the set of detected wave folders.

Basic run:

```bash
python3 scripts/build_run_provenance.py
```

Outputs:
- `reports/run_provenance.md`
- `reports/run_provenance.json`

## Script: export_methods_appendix.py

Purpose:
- Exports appendix-ready methods artifacts directly from the implemented code and rule spec.
- Produces rule tables, regex tables, anonymization tables, PEW selection-rule tables, and a decision-audit Markdown.

Basic run:

```bash
python3 scripts/export_methods_appendix.py
```

Arguments:
- `--spec` default `data/reference/methods/filter_spec.json`.
- `--topic-spec` default `data/reference/methods/topic_keywords.json`.
- `--outdir` default `reports/methods`.
- `--raw` default `data/raw/trump_archive_me2bert_filtered_2021.csv`.
- `--posts-clean` default `data/interim/preprocessing/posts_clean.csv`.
- `--posts-validated` default `data/interim/preprocessing/posts_topic_validated.csv`.
- `--posts-prompt` default `data/interim/preprocessing/posts_prompt_ready.csv`.
- `--pew-rq4` default `data/interim/pew/pew_rq4_inventory.csv`.

Outputs in `reports/methods/`:
1. `filter_table.csv`
2. `topic_patterns.csv` (topic regexes + rationale + source_basis + cross-script reuse flags)
3. `anonymization_rules.csv`
4. `pew_selection_rules.csv`
5. `decision_audit.md`

## Script: export_publishable_reports.py

Purpose:
- Copies publishable report artifacts from `reports/` into `docs/artifacts/`.
- Sanitizes local-path details before publishing.

Basic run:

```bash
python3 scripts/export_publishable_reports.py --overwrite
```

Outputs in `docs/artifacts/`:
1. `methods/filter_table.csv`
2. `methods/topic_patterns.csv`
3. `methods/anonymization_rules.csv`
4. `methods/pew_selection_rules.csv`
5. `methods/decision_audit.md`
6. `pipeline_summary.md`
7. `pipeline_summary.json`
8. `run_provenance.md`
9. `run_provenance.json`
10. `artifact_manifest.json`
11. `README.md`

## Script: validate_topic_rules.py

Purpose:
- Validates the canonical topic-keyword registry before extraction/filtering.
- Checks schema, topic uniqueness, and regex compile validity.

Basic run:

```bash
python3 scripts/validate_topic_rules.py
```

Arguments:
- `--spec` default `data/reference/methods/topic_keywords.json`.

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
- `--skip-methods` skip methods appendix artifact generation.
- `--skip-publishable` skip export of sanitized publishable artifacts.
- `--no-log` disable automatic tee logging to `logs/`.
- `--log-file PATH` custom log file path (default timestamped file under `logs/`).
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

3. Validate shared topic keyword registry:

```bash
python3 scripts/validate_topic_rules.py
```

4. Build all wave partials:

```bash
for d in data/pew_datasets/W*; do
  python3 scripts/build_pew_inventory.py --wave-folder "$d" --overwrite
done
```

5. Merge all partials:

```bash
python3 scripts/merge_pew_inventories.py --overwrite
```

6. Build deterministic RQ4 selection table:

```bash
python3 scripts/select_pew_for_rq4.py --overwrite
```

7. Preprocess posts:

```bash
python3 scripts/preprocess_posts.py
```

8. Check topic overlap between PEW and prompt-ready posts:

```bash
python3 scripts/report_topic_overlap.py
```

9. Build final topics plus both final subsets:

```bash
python3 scripts/build_rq4_final_subsets.py --overwrite
```

10. Build run provenance artifact:

```bash
python3 scripts/build_run_provenance.py
```

11. Build summary artifacts:

```bash
python3 scripts/build_pipeline_summary.py
```

12. Export methods appendix artifacts:

```bash
python3 scripts/export_methods_appendix.py
```

13. Export sanitized publishable artifacts:

```bash
python3 scripts/export_publishable_reports.py --overwrite
```

14. Optionally rerun post preprocessing with manual overrides:

```bash
python3 scripts/preprocess_posts.py --manual-review-csv manual_review_overrides.csv
```

## Methods Reproducibility

Rule provenance and audit artifacts are fully script-generated:
1. Canonical rule specification:
   - `data/reference/methods/filter_spec.json`
2. Canonical topic-keyword registry:
   - `data/reference/methods/topic_keywords.json`
3. Code-level rule implementation:
   - `scripts/preprocess_posts.py`
   - `scripts/select_pew_for_rq4.py`
   - `scripts/topic_rules.py`
4. Appendix-ready exports:
    - `reports/methods/filter_table.csv`
    - `reports/methods/topic_patterns.csv`
    - `reports/methods/anonymization_rules.csv`
    - `reports/methods/pew_selection_rules.csv`
    - `reports/methods/decision_audit.md`

## Limitations

Two methodological constraints remain explicit in this repository:

1. Upstream moral labels:
   - `preprocess_posts.py` uses the input column `is_morally_relevant` as an upstream filter.
   - This repository does not recreate that label; it treats it as an external input assumption that should be documented in the paper.

2. Conservative regex matching:
   - Topic assignment is intentionally high-precision and deterministic rather than recall-maximizing.
   - Some substantively relevant posts or PEW items may be missed when they do not contain the registry terms in `data/reference/methods/topic_keywords.json`.

Recommended for paper appendix generation:
1. Run `scripts/run_full_pipeline.sh`.
2. Use `reports/methods/*.csv` as table sources.
3. Use `reports/methods/decision_audit.md` for count-level decision trace.

## Common Issues

- `Preflight failed: at least one wave row is missing required files`:
  - check `reports/wave_preflight_report.csv`; current rule is `.sav` required and `readme` warning-only.
- `Codebook loaded: no (pypdf_unavailable)`:
  - install `pypdf` in the same Python environment used by `python3`.
- `Output already exists ...`:
  - rerun with `--overwrite`.
- `No partial inventory files matched` in merge step:
  - confirm each wave folder has `pew_question_inventory_partial.csv`.
- Manual overrides error:
  - the override CSV must include an `id` column.
