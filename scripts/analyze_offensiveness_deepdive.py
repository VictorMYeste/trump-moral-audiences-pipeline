#!/usr/bin/env python3
"""Offensiveness deep-dive over RQ1 bundle-level labels (ARR rebuttal, reviewer 2v7f W4).

# Simple explanation of this script (step by step):
# 1) Read the flat bundle-level label table produced by `analyze_rq1_labels.py`
#    (one row = one persona x one topic-matched bundle judgment, low-temperature runs,
#    parse errors already excluded upstream).
# 2) Keep rows where offensiveness, legitimacy, and endorsement parse as numbers.
# 3) Table A: per topic, pooled over all selection strategies and persona positions,
#    compute n and mean offensiveness / legitimacy / endorsement.
# 4) Table B: per topic x stance, compute n and mean offensiveness (tone penalty of
#    rejecting vs supporting responses).
# 5) Table C: per topic x selection strategy (mode+variant), compute n and mean
#    offensiveness, to check the topic ordering is not driven by one strategy.
# 6) Write the three CSVs next to the input and print Tables A and B.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

DEFAULT_INPUT = "docs/private/RQ1/RQ1_all_label_analysis/rq1_bundle_labels_flat.csv"
DEFAULT_OUTPUT_DIR = "docs/private/RQ1/RQ1_all_label_analysis"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    by_topic: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    by_topic_stance: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_topic_config: dict[tuple[str, str], list[float]] = defaultdict(list)

    with open(args.input, newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                off = float(row["offensiveness"])
                leg = float(row["legitimacy"])
                endo = float(row["endorsement"])
            except (ValueError, KeyError):
                continue
            topic = row["topic"]
            by_topic[topic]["offensiveness"].append(off)
            by_topic[topic]["legitimacy"].append(leg)
            by_topic[topic]["endorsement"].append(endo)
            by_topic_stance[(topic, row["stance"])].append(off)
            by_topic_config[(topic, f"{row['mode']}-{row['variant']}")].append(off)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    path_a = output_dir / "rq1_tone_by_topic.csv"
    with open(path_a, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["topic", "n", "mean_offensiveness", "mean_legitimacy", "mean_endorsement"])
        for topic in sorted(by_topic):
            labels = by_topic[topic]
            writer.writerow(
                [
                    topic,
                    len(labels["offensiveness"]),
                    round(statistics.mean(labels["offensiveness"]), 4),
                    round(statistics.mean(labels["legitimacy"]), 4),
                    round(statistics.mean(labels["endorsement"]), 4),
                ]
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
        writer.writerow(["topic", "config", "n", "mean_offensiveness"])
        for (topic, config), values in sorted(by_topic_config.items()):
            writer.writerow([topic, config, len(values), round(statistics.mean(values), 4)])

    print(f"Table A (pooled tone labels by topic) -> {path_a}")
    for topic in sorted(by_topic):
        labels = by_topic[topic]
        print(
            f"  {topic:35s} n={len(labels['offensiveness']):5d} "
            f"off={statistics.mean(labels['offensiveness']):.2f} "
            f"leg={statistics.mean(labels['legitimacy']):.2f} "
            f"end={statistics.mean(labels['endorsement']):.2f}"
        )
    print(f"Table B (offensiveness by topic x stance) -> {path_b}")
    for (topic, stance), values in sorted(by_topic_stance.items()):
        print(f"  {topic:35s} {stance:8s} n={len(values):5d} off={statistics.mean(values):.2f}")
    print(f"Table C (offensiveness by topic x config) -> {path_c}")


if __name__ == "__main__":
    main()
