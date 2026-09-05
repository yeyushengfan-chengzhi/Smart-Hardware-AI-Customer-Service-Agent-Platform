from app.services.benchmark_service import evaluate_benchmark, load_benchmark


def test_benchmark_is_versioned_and_documents_limitations():
    benchmark = load_benchmark()

    assert benchmark["meta"]["version"] == "1.0.0"
    assert "production accuracy" in benchmark["meta"]["limitations"]
    assert len(benchmark["cases"]) == 20
    assert all(case["provenance"] for case in benchmark["cases"])


def test_benchmark_reports_each_supported_task():
    report = evaluate_benchmark()

    assert set(report["tasks"]) == {"route", "safety", "diagnosis"}
    assert report["case_count"] == 20
    assert all(metric["total"] > 0 for metric in report["tasks"].values())


def test_enhanced_system_beats_generic_rag_baseline_on_domain_tasks():
    report = evaluate_benchmark()

    assert report["enhanced_overall"] > report["baseline_overall"]
    assert report["tasks"]["safety"]["enhanced_score"] == 1
    assert report["tasks"]["diagnosis"]["enhanced_score"] == 1


def test_every_result_preserves_provenance():
    report = evaluate_benchmark()

    assert all(row["provenance"] for row in report["results"])
