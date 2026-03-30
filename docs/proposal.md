# Study Proposal

This document summarizes the public, reproducible study design for the Trump moral-audience project.

## 1. Research Goal

Primary research question:
- Do synthetic audiences respond differently to the same morally salient political messages when identity is anonymized and content is controlled by topic and period?

Design principle:
- Compare responses to the same message bundles across audience personas, not general impressions of a political figure.

## 2. Data Assets

Post corpus input:
- `data/raw/trump_archive_me2bert_filtered_2009_2021.csv`
- `data/raw/trump_manual_me2bert_filtered_2022_2024.csv`

Post corpus source:
- Current window source: Kaggle dataset `headsortails/trump-twitter-archive`
  - URL: <https://www.kaggle.com/datasets/headsortails/trump-twitter-archive>
  - URL (plain): https://www.kaggle.com/datasets/headsortails/trump-twitter-archive
- Planned extension source: The Trump Archive
  - URL: <https://www.thetrumparchive.com/>
  - URL (plain): https://www.thetrumparchive.com/
- Current implemented windows:
- `2009-05-12` to `2021-01-08`
- `2022-04-29` to `2024-11-04`

PEW wave inputs:
- `data/pew_datasets/W*/` (per-wave folders containing `.sav`, readme, and optional PDFs)

Key generated assets:
- `data/interim/preprocessing/posts_prompt_ready.csv`
- `data/interim/preprocessing/posts_moderation_analysis.csv`
- `data/interim/pew/pew_question_inventory.csv`
- `data/interim/pew/pew_rq4_inventory.csv`
- `data/interim/rq4/rq4_topics_final.csv`
- `data/interim/rq4/rq4_pew_subset.csv`
- `data/interim/rq4/rq4_posts_subset.csv`

## 3. Core Method Decisions

1. Use deterministic, PEW-oriented issue topics instead of unsupervised topic discovery.
   - Topic regexes are centralized in `data/reference/methods/topic_keywords.json` and reused by both PEW and post filters.
2. Keep deleted/flagged posts in the analytical archive, but exclude them from the prompt-ready pool.
3. Apply identity anonymization that preserves issue meaning.
4. Require topic overlap between included PEW rows and prompt-ready posts before final subsetting.

## 4. Dual-Track Dataset Strategy

Track A: Prompting dataset
- Goal: high internal validity for controlled prompting.
- Source: `posts_prompt_ready.csv`.
- Excludes moderation-status rows and low-quality/ambiguous rows.

Track B: Moderation-status analysis dataset
- Goal: compare lexical/topic patterns by moderation status.
- Source: `posts_moderation_analysis.csv`.
- Retains `deleted`, `flagged`, and `deleted_and_flagged` labels.

This separation avoids conflating moderation status with prompt-response measurement.

## 5. PEW Compatibility Strategy

Selection is deterministic and script-based:
- `scripts/select_pew_for_rq4.py`

A PEW row is included only when all conditions hold:
1. Trump-targeted item.
2. Supported judgment family (`approval`, `confidence`, or `policy_support`).
3. Not in excluded forms (thermometer, trait, affective reaction, knowledge-only, broad favorability).
4. Exactly one issue-topic match.

Output includes transparent diagnostics:
- `include_for_rq4`
- `exclude_code`
- `rule_trace`

## 6. Final Topic and Subset Construction

1. Compute topic overlap:
   - `scripts/report_topic_overlap.py`
2. Build final overlap-constrained subsets:
   - `scripts/build_rq4_final_subsets.py`

Final comparison datasets (`rq4_pew_subset.csv`, `rq4_posts_subset.csv`) are restricted to the same topic set listed in `rq4_topics_final.csv`.

## 7. Reproducible Execution

Run the full pipeline:

```bash
scripts/run_full_pipeline.sh
```

Optional thresholds:

```bash
scripts/run_full_pipeline.sh --min-pew-per-topic 2 --min-posts-per-topic 50
```

## 8. Interpretation and Limitations

1. Moderation flags/deletions are observational metadata; causal reasons for deletion/flagging cannot be inferred from this dataset alone.
2. Topic matching is regex-based and deterministic, prioritizing auditability over semantic recall.
3. Inclusion rates depend on available PEW waves and questionnaire content.

## 9. Reproducibility Standard

The project is reproducible when:
1. Script versions are fixed in the repository.
2. Inputs are present in documented locations.
3. Outputs can be regenerated from raw inputs with `scripts/run_full_pipeline.sh`.
4. Methods appendix artifacts are regenerated from code/spec with `scripts/export_methods_appendix.py`.

Appendix-ready methods artifacts:
- `reports/methods/filter_table.csv`
- `reports/methods/topic_patterns.csv`
- `reports/methods/anonymization_rules.csv`
- `reports/methods/pew_selection_rules.csv`
- `reports/methods/decision_audit.md`
