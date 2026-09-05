"""Offline benchmark for routing, safety and adaptive diagnostic decisions."""

from __future__ import annotations

import json
from pathlib import Path

from app.agents.supervisor_agent import supervisor_agent
from app.services.adaptive_diagnosis_service import adaptive_diagnosis_service


BENCHMARK_PATH = (
    Path(__file__).resolve().parents[3]
    / "data_sources"
    / "evaluation"
    / "hw_support_bench_v1.json"
)


def load_benchmark(path: Path = BENCHMARK_PATH) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not payload.get("meta") or not isinstance(payload.get("cases"), list):
        raise ValueError("invalid benchmark dataset")
    return payload


def evaluate_benchmark() -> dict:
    benchmark = load_benchmark()
    results = []
    for case in benchmark["cases"]:
        evaluator = {
            "route": _evaluate_route,
            "safety": _evaluate_safety,
            "diagnosis": _evaluate_diagnosis,
        }[case["task"]]
        results.append(evaluator(case))

    tasks = {}
    for task in ("route", "safety", "diagnosis"):
        rows = [row for row in results if row["task"] == task]
        enhanced_passed = sum(row["enhanced_passed"] for row in rows)
        baseline_passed = sum(row["baseline_passed"] for row in rows)
        tasks[task] = {
            "total": len(rows),
            "enhanced_passed": enhanced_passed,
            "enhanced_score": _rate(enhanced_passed, len(rows)),
            "baseline_passed": baseline_passed,
            "baseline_score": _rate(baseline_passed, len(rows)),
        }

    return {
        "benchmark": benchmark["meta"],
        "case_count": len(results),
        "enhanced_overall": round(
            sum(item["enhanced_score"] for item in tasks.values()) / len(tasks), 4
        ),
        "baseline_overall": round(
            sum(item["baseline_score"] for item in tasks.values()) / len(tasks), 4
        ),
        "tasks": tasks,
        "results": results,
    }


def _evaluate_route(case: dict) -> dict:
    query = case["input"]["query"]
    expected = case["expected"]["route"]
    enhanced = supervisor_agent.route(query)["route"]
    baseline = _generic_rag_route(query)
    return _result(case, expected, baseline, enhanced)


def _evaluate_safety(case: dict) -> dict:
    request = case["input"]
    expected = case["expected"]["status"]
    enhanced_result = adaptive_diagnosis_service.next_check(
        request["query"], request["fault_type"], []
    )
    enhanced = enhanced_result["status"]
    # A plain RAG chatbot has no deterministic pre-generation safety interrupt.
    baseline = "continue_answer"
    return _result(case, expected, baseline, enhanced)


def _evaluate_diagnosis(case: dict) -> dict:
    request = case["input"]
    expected = case["expected"]["top_hypothesis"]
    enhanced_result = adaptive_diagnosis_service.next_check(
        request["query"], request["fault_type"], request["observations"]
    )
    enhanced = enhanced_result["hypotheses"][0]["code"]
    # A static checklist does not update a ranked cause from observations.
    baseline = "no_ranked_hypothesis"
    return _result(case, expected, baseline, enhanced)


def _result(case: dict, expected: str, baseline: str, enhanced: str) -> dict:
    return {
        "id": case["id"],
        "task": case["task"],
        "expected": expected,
        "baseline": baseline,
        "enhanced": enhanced,
        "baseline_passed": baseline == expected,
        "enhanced_passed": enhanced == expected,
        "provenance": case.get("provenance", []),
    }


def _generic_rag_route(query: str) -> str:
    """Minimal baseline: send in-domain questions to one knowledge chain."""
    hardware_terms = (
        "主板", "显卡", "内存", "cpu", "bios", "机箱", "风冷", "水冷",
        "开机", "画面", "温度", "电源", "硬件",
    )
    normalized = query.casefold()
    return "knowledge" if any(term in normalized for term in hardware_terms) else "GeneralAgent"


def _rate(passed: int, total: int) -> float:
    return round(passed / total, 4) if total else 0.0
