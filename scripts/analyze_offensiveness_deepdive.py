#!/usr/bin/env python3
"""Secondary reception labels deep-dive over RQ1 bundle-level labels (ARR rebuttal, reviewer 2v7f W4).

# Simple explanation of this script (step by step):
# 1) Read the flat bundle-level label table produced by `analyze_rq1_labels.py`
#    (one row = one persona x one topic-matched bundle judgment, low-temperature runs,
#    parse errors already excluded upstream).
# 2) Keep rows where the four scalar labels parse as numbers.
# 3) Table A: per topic, pooled over all selection strategies and persona positions,
#    compute n and mean agreement / legitimacy / offensiveness / endorsement.
# 4) Table B: per topic x stance, compute n and mean offensiveness (tone penalty of
#    rejecting vs supporting responses).
# 5) Table C: per topic x selection strategy, compute n and mean offensiveness, to check
#    the topic ordering is not driven by one strategy.
# 6) Table D: per selection strategy x topic, the high-minus-low persona-position contrast
#    on stance and on each scalar label. `persona_polarity` positive/neutral/negative are
#    the paper's high/mid/low positions (verified: MFT Immigration/border reproduces the
#    -0.95 / +0.93 top-5 mean stance reported in Section 5.1).
# 7) Table A2: the same per-topic means at message (tweet) level, as the robustness
#    check the RQ1 analysis section promises for the scalar labels.
# 8) Write the five CSVs next to the input and print Tables A, A2, B and D.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

DEFAULT_INPUT = "docs/private/RQ1/RQ1_all_label_analysis/rq1_bundle_labels_flat.csv"
DEFAULT_TWEET_INPUT = "docs/private/RQ1/RQ1_all_label_analysis/rq1_tweet_labels_flat.csv"
DEFAULT_OUTPUT_DIR = "docs/private/RQ1/RQ1_all_label_analysis"

SCALAR_LABELS = ["agreement", "legitimacy", "offensiveness", "endorsement"]
POLARITY_TO_POSITION = {"positive": "high", "neutral": "mid", "negative": "low"}
CONFIG_TO_STRATEGY = {"iw-neigh": "IW-neigh", "iw-topk": "IW-contour", "mft-topk": "MFT"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--tweet-input", default=DEFAULT_TWEET_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    by_topic: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_topic_stance: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_topic_config: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_cell: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )

    with open(args.input, newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                values = {label: float(row[label]) for label in SCALAR_LABELS}
                values["stance_score"] = float(row["stance_score"])
            except (ValueError, KeyError):
                continue
            topic = row["topic"]
            strategy = CONFIG_TO_STRATEGY[f"{row['mode']}-{row['variant']}"]
            position = POLARITY_TO_POSITION[row["persona_polarity"]]
            for label in SCALAR_LABELS:
                by_topic[topic][label].append(values[label])
            by_topic_stance[(topic, row["stance"])].append(values["offensiveness"])
            by_topic_config[(topic, strategy)].append(values["offensiveness"])
            for label, value in values.items():
                by_cell[(strategy, topic, position)][label].append(value)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    path_a = output_dir / "rq1_tone_by_topic.csv"
    with open(path_a, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic", "n"] + [f"mean_{label}" for label in SCALAR_LABELS])
        for topic in sorted(by_topic):
            labels = by_topic[topic]
            writer.writerow(
                [topic, len(labels["offensiveness"])]
                + [round(statistics.mean(labels[label]), 4) for label in SCALAR_LABELS]
            )

    by_topic_tweet: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    with open(args.tweet_input, newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                values = {label: float(row[label]) for label in SCALAR_LABELS}
            except (ValueError, KeyError):
                continue
            for label in SCALAR_LABELS:
                by_topic_tweet[row["topic"]][label].append(values[label])

    path_a2 = output_dir / "rq1_tone_by_topic_tweet.csv"
    with open(path_a2, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic", "n"] + [f"mean_{label}" for label in SCALAR_LABELS])
        for topic in sorted(by_topic_tweet):
            labels = by_topic_tweet[topic]
            writer.writerow(
                [topic, len(labels["offensiveness"])]
                + [round(statistics.mean(labels[label]), 4) for label in SCALAR_LABELS]
            )

    path_b = output_dir / "rq1_offensiveness_by_topic_stance.csv"
    with open(path_b, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic", "stance", "n", "mean_offensiveness"])
        for (topic, stance), values in sorted(by_topic_stance.items()):
            writer.writerow([topic, stance, len(values), round(statistics.mean(values), 4)])

    path_c = output_dir / "rq1_offensiveness_by_topic_config.csv"
    with open(path_c, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic", "strategy", "n", "mean_offensiveness"])
        for (topic, strategy), values in sorted(by_topic_config.items()):
            writer.writerow([topic, strategy, len(values), round(statistics.mean(values), 4)])

    path_d = output_dir / "rq1_high_low_contrasts_by_label.csv"
    contrasts: dict[tuple[str, str], dict[str, float]] = {}
    with open(path_d, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["strategy", "topic", "n_high", "n_low", "contrast_stance"]
            + [f"contrast_{label}" for label in SCALAR_LABELS]
        )
        for strategy in ["IW-neigh", "IW-contour", "MFT"]:
            for topic in sorted(by_topic):
                high = by_cell.get((strategy, topic, "high"))
                low = by_cell.get((strategy, topic, "low"))
                if not high or not low:
                    continue
                cell = {
                    label: statistics.mean(high[label]) - statistics.mean(low[label])
                    for label in ["stance_score"] + SCALAR_LABELS
                }
                contrasts[(strategy, topic)] = cell
                writer.writerow(
                    [strategy, topic, len(high["stance_score"]), len(low["stance_score"])]
                    + [round(cell[label], 4) for label in ["stance_score"] + SCALAR_LABELS]
                )

    print(f"Table A (pooled scalar labels by topic) -> {path_a}")
    header = " ".join(f"{label[:5]:>6s}" for label in SCALAR_LABELS)
    print(f"  {'topic':35s} {'n':>5s} {header}")
    for topic in sorted(by_topic):
        labels = by_topic[topic]
        means = " ".join(f"{statistics.mean(labels[label]):6.2f}" for label in SCALAR_LABELS)
        print(f"  {topic:35s} {len(labels['offensiveness']):5d} {means}")

    print(f"Table A2 (pooled scalar labels by topic, tweet level) -> {path_a2}")
    for topic in sorted(by_topic_tweet):
        labels = by_topic_tweet[topic]
        means = " ".join(f"{statistics.mean(labels[label]):6.2f}" for label in SCALAR_LABELS)
        print(f"  {topic:35s} {len(labels['offensiveness']):5d} {means}")

    print(f"Table B (offensiveness by topic x stance) -> {path_b}")
    for (topic, stance), values in sorted(by_topic_stance.items()):
        print(f"  {topic:35s} {stance:8s} n={len(values):5d} off={statistics.mean(values):.2f}")

    print(f"Table C (offensiveness by topic x strategy) -> {path_c}")

    print(f"Table D (high-minus-low contrasts) -> {path_d}")
    print(f"  {'strategy':11s} {'topic':35s} {'stance':>7s} " + header)
    for (strategy, topic), cell in contrasts.items():
        row = " ".join(f"{cell[label]:+6.2f}" for label in SCALAR_LABELS)
        print(f"  {strategy:11s} {topic:35s} {cell['stance_score']:+7.2f} {row}")


if __name__ == "__main__":
    main()
