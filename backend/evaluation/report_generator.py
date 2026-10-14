"""
VIDYA-X AI — Evaluation Report Generator & Quality Release Gates (Step 13)

Evaluates quality release gates, serializes case results and aggregated metrics,
and writes structured reports (run_metadata.json, case_results.jsonl, metrics_summary.json, report.md).
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List

from evaluation.config import QUALITY_GATES, RESULTS_DIR
from evaluation.schemas import (
    MetricResult,
    CaseEvaluationResult,
    QualityGateResult,
    EvaluationRunSummary,
)

logger = logging.getLogger(__name__)


def evaluate_quality_gates(metrics: Dict[str, MetricResult]) -> List[QualityGateResult]:
    """Check calculated metrics against configured release gate thresholds."""
    gate_results = []
    for metric_name, threshold in QUALITY_GATES.items():
        if metric_name in metrics:
            m = metrics[metric_name]
            actual = m.result
            if "violation_count" in metric_name:
                passed = actual <= threshold
            else:
                passed = actual >= threshold

            gate_results.append(QualityGateResult(
                gate_name=f"Gate: {metric_name}",
                metric_name=metric_name,
                threshold=threshold,
                actual_value=actual,
                passed=passed,
            ))
    return gate_results


def generate_evaluation_report(
    run_id: str,
    dataset_version: str,
    deterministic_only: bool,
    case_results: List[CaseEvaluationResult],
    metrics: Dict[str, MetricResult],
    output_dir: str = RESULTS_DIR,
) -> EvaluationRunSummary:
    """
    Generate evaluation artifacts and write report summary.
    """
    now_str = datetime.now(timezone.utc).isoformat()
    run_dir = os.path.join(output_dir, f"run_{run_id}")
    os.makedirs(run_dir, exist_ok=True)

    total_cases = len(case_results)
    passed_cases = sum(1 for c in case_results if c.passed)
    failed_cases = total_cases - passed_cases
    pass_pct = round((passed_cases / float(total_cases) * 100), 1) if total_cases > 0 else 0.0

    # Evaluate Quality Gates
    gates = evaluate_quality_gates(metrics)
    failed_gate_names = [g.gate_name for g in gates if not g.passed]
    all_gates_passed = len(failed_gate_names) == 0

    summary = EvaluationRunSummary(
        run_id=run_id,
        dataset_version=dataset_version,
        timestamp=now_str,
        deterministic_only=deterministic_only,
        total_cases=total_cases,
        passed_cases=passed_cases,
        failed_cases=failed_cases,
        pass_rate_percentage=pass_pct,
        metrics=metrics,
        quality_gates=gates,
        quality_gates_passed=all_gates_passed,
        gate_failures=failed_gate_names,
    )

    # 1. Write run_metadata.json
    meta_path = os.path.join(run_dir, "run_metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(summary.model_dump(), f, indent=2)

    # 2. Write case_results.jsonl
    cases_path = os.path.join(run_dir, "case_results.jsonl")
    with open(cases_path, "w", encoding="utf-8") as f:
        for c in case_results:
            f.write(json.dumps(c.model_dump()) + "\n")

    # 3. Write metrics_summary.json
    metrics_path = os.path.join(run_dir, "metrics_summary.json")
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({k: v.model_dump() for k, v in metrics.items()}, f, indent=2)

    # 4. Write report.md
    report_md_path = os.path.join(run_dir, "report.md")
    _write_markdown_report(report_md_path, summary, case_results)

    logger.info(f"Evaluation report generated successfully at: {run_dir}")
    return summary


def _write_markdown_report(
    filepath: str,
    summary: EvaluationRunSummary,
    case_results: List[CaseEvaluationResult],
):
    """Format and write human-readable Markdown evaluation report."""
    gate_status_badge = "✅ PASSED" if summary.quality_gates_passed else "❌ FAILED"

    lines = [
        f"# VIDYA-X AI Benchmark Evaluation Report",
        f"",
        f"**Run ID:** `{summary.run_id}`  ",
        f"**Timestamp:** `{summary.timestamp}`  ",
        f"**Dataset Version:** `{summary.dataset_version}`  ",
        f"**Mode:** `{'Deterministic-Only' if summary.deterministic_only else 'Full Evaluation'}`  ",
        f"**Overall Quality Release Gate:** {gate_status_badge}  ",
        f"",
        f"---",
        f"",
        f"## 1. Benchmark Execution Summary",
        f"",
        f"| Metric | Value |",
        f"| :--- | :---: |",
        f"| **Total Cases Evaluated** | {summary.total_cases} |",
        f"| **Passed Cases** | {summary.passed_cases} |",
        f"| **Failed Cases** | {summary.failed_cases} |",
        f"| **Pass Rate** | **{summary.pass_rate_percentage}%** |",
        f"",
        f"---",
        f"",
        f"## 2. Quality Release Gates",
        f"",
        f"| Gate Name | Metric | Required Threshold | Actual Measured | Gate Status |",
        f"| :--- | :--- | :---: | :---: | :---: |",
    ]

    for g in summary.quality_gates:
        st = "✅ PASSED" if g.passed else "❌ FAILED"
        lines.append(f"| {g.gate_name} | `{g.metric_name}` | `{g.threshold}` | `{g.actual_value}` | {st} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 3. Aggregated System Metrics",
        f"",
        f"| Metric Name | Category | Measured Result | Benchmark Target | Metric Status |",
        f"| :--- | :--- | :---: | :---: | :---: |",
    ])

    for k, m in summary.metrics.items():
        st = "✅ PASSED" if m.status == "passed" else "❌ FAILED"
        target_str = str(m.benchmark_target) if m.benchmark_target is not None else "N/A"
        lines.append(f"| `{m.metric_name}` | {m.category} | **{m.result}** | {target_str} | {st} |")

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 4. Case-by-Case Execution Details",
        f"",
        f"| Case ID | Task Type | Outcome | Score | Details |",
        f"| :--- | :--- | :---: | :---: | :--- |",
    ])

    for c in case_results:
        st = "✅ PASS" if c.passed else "❌ FAIL"
        det_str = ", ".join(f"{k}={v}" for k, v in c.details.items() if k != "retrieved_ids")
        lines.append(f"| `{c.case_id}` | `{c.task_type}` | {st} | `{c.score}` | {det_str[:60]} |")

    lines.append("")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
