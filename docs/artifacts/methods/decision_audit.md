# Decision Audit

Generated (UTC): `2026-03-30T12:44:10.731847+00:00`
Rule spec version: `1.0.0`

## Stage Counts

| metric | value |
| --- | --- |
| raw_input_rows | 22822 |
| posts_clean_rows | 17497 |
| posts_topic_validated_rows | 17497 |
| posts_prompt_ready_rows | 3718 |
| pew_rq4_rows | 981 |
| pew_include_yes | 93 |
| pew_include_no | 888 |
| hard_drop_inferred | 5325 |

## Post Exclusion Reasons

| exclude_reason | count |
| --- | --- |
| other_campaign_generic | 11371 |
| truncated_or_context_dependent | 2395 |
| multi_topic_ambiguous | 1494 |
| excluded_from_prompt_due_to_moderation_status | 374 |
| identity_leak_after_anonymization | 156 |
| anonymization_degraded_text | 52 |
| duplicate_after_cleaning | 20 |

## Post Keep and Moderation Counts

| keep_for_prompt | count |
| --- | --- |
| no | 13779 |
| yes | 3718 |

| moderation_status | count |
| --- | --- |
| deleted | 267 |
| flagged | 107 |
| not_deleted_not_flagged | 17123 |

## PEW Exclusion Codes

| exclude_code | count |
| --- | --- |
| exclude_not_trump_target | 466 |
| exclude_judgment_not_supported | 304 |
| exclude_affective_reaction | 47 |
| exclude_trait | 39 |
| exclude_no_topic_match | 19 |
| exclude_multi_topic_ambiguous | 5 |
| exclude_knowledge_or_awareness | 5 |
| exclude_thermometer | 2 |
| exclude_broad_favorability | 1 |

## Topic Overlap

| topic | pew_included_rows | prompt_ready_rows |
| --- | --- | --- |
| covid_public_health | 5 | 232 |
| economy_jobs_trade | 75 | 922 |
| foreign_policy_national_security | 5 | 916 |
| immigration_border | 4 | 401 |
| judiciary_courts | 4 | 130 |
