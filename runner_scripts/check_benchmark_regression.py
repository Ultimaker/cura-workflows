#!/usr/bin/env python3
"""
Compares the benchmark results that were just pushed to the GitHub Pages benchmark data
repository against the average of the preceding N runs for the same benchmark suite,
instead of only the single previous run. This smooths out run-to-run noise that is common
on GitHub-hosted runners.

This script never handles GitHub tokens: it only reads the data.js file that the "Store
benchmark result" step already checked out and pushed, and writes its findings to a file
and job outputs. Posting a comment, if any, is left to a dedicated GitHub Action step that
owns the token.
"""

import argparse
import json
import os
import statistics
import sys
from pathlib import Path

SCRIPT_PREFIX = "window.BENCHMARK_DATA = "

# Tools for which a smaller benchmark value is better. Anything not listed here is
# treated as bigger-is-better. Mirrors the mapping used by benchmark-action/github-action-benchmark.
SMALLER_IS_BETTER_TOOLS = {
    "cargo", "go", "benchmarkluau", "googlecpp", "catch2", "julia", "jmh",
    "benchmarkdotnet", "customSmallerIsBetter",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-js-path", required=True, help="Path to the data.js file to read history from")
    parser.add_argument("--name", required=True, help="Benchmark suite name")
    parser.add_argument("--tool", required=True, help="Benchmark tool identifier")
    parser.add_argument("--baseline-runs", type=int, default=10, help="Number of previous runs to average over")
    parser.add_argument("--alert-threshold", default="150%", help='e.g. "150%"')
    parser.add_argument("--cc-users", default="", help="Comma separated users to mention, e.g. '@a, @b'")
    parser.add_argument("--comment-body-path", required=True, help="Where to write the alert comment body, if any")
    return parser.parse_args()


def load_entries(data_js_path: Path, name: str) -> list:
    content = data_js_path.read_text(encoding="utf-8")
    json_text = content[len(SCRIPT_PREFIX):].strip().rstrip(";")
    data = json.loads(json_text)
    return data.get("entries", {}).get(name, [])


def parse_threshold(threshold: str) -> float:
    return float(threshold.strip().rstrip("%")) / 100.0


def worse_ratio(reference: float, current: float, bigger_is_better: bool) -> float:
    """Ratio above 1 means the current value is worse than the reference."""
    numerator, denominator = (reference, current) if bigger_is_better else (current, reference)
    if denominator == 0:
        return 1.0 if numerator == 0 else float("inf")
    return numerator / denominator


def compare_runs(entries: list, baseline_runs: int, tool: str) -> list:
    current = entries[-1]
    baseline_entries = entries[max(0, len(entries) - 1 - baseline_runs):-1]
    last_values = {b["name"]: b["value"] for b in entries[-2]["benches"]}
    bigger_is_better = tool not in SMALLER_IS_BETTER_TOOLS

    rows = []
    for bench in current["benches"]:
        history = [
            b["value"]
            for entry in baseline_entries
            for b in entry["benches"]
            if b["name"] == bench["name"]
        ]
        average = statistics.mean(history) if history else None
        last_value = last_values.get(bench["name"])

        rows.append({
            "name": bench["name"],
            "unit": bench["unit"],
            "current": bench["value"],
            "average": average,
            "sample_count": len(history),
            "average_ratio": worse_ratio(average, bench["value"], bigger_is_better) if average is not None else None,
            "last": last_value,
            "last_ratio": worse_ratio(last_value, bench["value"], bigger_is_better) if last_value is not None else None,
        })

    return rows


def find_alerts(rows: list, threshold: float) -> list:
    return [r for r in rows if r["average_ratio"] is not None and r["average_ratio"] > threshold]


def format_change(ratio: float | None) -> str:
    if ratio is None:
        return "n/a"
    if ratio == float("inf"):
        return "+inf%"
    return f"{(ratio - 1) * 100:+.1f}%"


def format_value(value: float | None, unit: str) -> str:
    return "n/a" if value is None else f"{value:.4g} {unit}"


def build_summary(rows: list, name: str, baseline_runs: int, threshold: float) -> str:
    lines = [
        f"## Benchmark variation: {name}",
        "",
        f"Current run compared with the average of up to {baseline_runs} previous runs, and with the previous run. "
        f"Positive change means worse. Alert threshold vs average: `{threshold * 100:.0f}%`.",
        "",
        "| Benchmark | Current | Average | Change vs average | Previous run | Change vs previous | Status |",
        "|-|-|-|-|-|-|-|",
    ]
    for row in rows:
        is_alert = row["average_ratio"] is not None and row["average_ratio"] > threshold
        lines.append(
            f"| `{row['name']}` | {format_value(row['current'], row['unit'])} "
            f"| {format_value(row['average'], row['unit'])} | {format_change(row['average_ratio'])} "
            f"| {format_value(row['last'], row['unit'])} | {format_change(row['last_ratio'])} "
            f"| {'**regression**' if is_alert else 'ok'} |"
        )
    lines.append("")
    return "\n".join(lines)


def build_comment_body(alerts: list, name: str, baseline_runs: int, threshold: float, cc_users: str) -> str:
    benchmark_text = "" if name == "Benchmark" else f" **'{name}'**"
    lines = [
        "# :warning: **Performance Alert** :warning:",
        "",
        f"Benchmark{benchmark_text} regressed compared to the "
        f"average of its last {baseline_runs} runs, exceeding the `{threshold * 100:.0f}%` alert threshold.",
        "",
        "| Benchmark | Current | Average (last N runs) | Ratio |",
        "|-|-|-|-|",
    ]
    for alert in alerts:
        lines.append(
            f"| `{alert['name']}` | `{alert['current']}` {alert['unit']} "
            f"| `{alert['average']:.2f}` {alert['unit']} (of {alert['sample_count']} runs) "
            f"| `{alert['average_ratio']:.2f}` |"
        )
    lines.append("")
    cc = [u.strip() for u in cc_users.split(",") if u.strip()]
    if cc:
        lines.append(f"CC: {' '.join(cc)}")
    return "\n".join(lines)


def set_output(name: str, value: str) -> None:
    github_output = os.environ.get("GITHUB_OUTPUT")
    if not github_output:
        return
    with open(github_output, "a", encoding="utf-8") as f:
        f.write(f"{name}={value}\n")


def main() -> int:
    args = parse_args()

    data_js_path = Path(args.data_js_path)
    if not data_js_path.is_file():
        print(f"::warning::Could not find benchmark data file at '{data_js_path}', skipping regression check.")
        set_output("has_alert", "false")
        return 0

    entries = load_entries(data_js_path, args.name)

    if len(entries) < 2:
        print(f"Not enough benchmark history for '{args.name}' yet, skipping regression check.")
        set_output("has_alert", "false")
        return 0

    threshold = parse_threshold(args.alert_threshold)
    rows = compare_runs(entries, args.baseline_runs, args.tool)
    summary = build_summary(rows, args.name, args.baseline_runs, threshold)

    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(summary + "\n")

    alerts = find_alerts(rows, threshold)

    if not alerts:
        print(f"No performance regression detected for '{args.name}' against the rolling average.")
        set_output("has_alert", "false")
        return 0

    for alert in alerts:
        print(
            f"::warning::Performance alert for '{alert['name']}': current value {alert['current']} "
            f"{alert['unit']} is {alert['average_ratio']:.2f}x worse than the average of the last "
            f"{alert['sample_count']} runs ({alert['average']:.2f} {alert['unit']}), "
            f"exceeding the {threshold * 100:.0f}% threshold."
        )

    body = build_comment_body(alerts, args.name, args.baseline_runs, threshold, args.cc_users)
    Path(args.comment_body_path).write_text(body, encoding="utf-8")
    set_output("has_alert", "true")

    return 0


if __name__ == "__main__":
    sys.exit(main())
