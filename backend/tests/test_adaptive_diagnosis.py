from app.services.adaptive_diagnosis_service import AdaptiveDiagnosisService


def test_first_check_is_selected_by_information_gain():
    result = AdaptiveDiagnosisService().next_check("主机开机黑屏", "no_display", [])

    assert result["status"] == "in_progress"
    assert result["next_check"]["check_id"] == "debug_led"
    assert result["next_check"]["information_gain"] > 0
    assert abs(sum(item["probability"] for item in result["hypotheses"]) - 1) < .001


def test_abnormal_memory_check_increases_memory_hypothesis():
    result = AdaptiveDiagnosisService().next_check(
        "主机开机黑屏",
        "no_display",
        [{"check_id": "memory_reseat", "outcome": "abnormal"}],
    )

    assert result["hypotheses"][0]["code"] == "memory_training"
    assert result["hypotheses"][0]["probability"] > .5
    assert result["next_check"]["check_id"] != "memory_reseat"


def test_normal_memory_check_reduces_memory_hypothesis():
    service = AdaptiveDiagnosisService()
    baseline = service.next_check("黑屏", "no_display", [])
    result = service.next_check(
        "黑屏", "no_display", [{"check_id": "memory_reseat", "outcome": "normal"}]
    )

    before = next(
        item for item in baseline["hypotheses"] if item["code"] == "memory_training"
    )
    after = next(
        item for item in result["hypotheses"] if item["code"] == "memory_training"
    )
    assert after["probability"] < before["probability"]


def test_safety_language_stops_diagnosis_and_requests_handoff():
    result = AdaptiveDiagnosisService().next_check(
        "电源冒烟还有焦味，怎么办", "boot_failure", []
    )

    assert result["status"] == "safety_stop"
    assert result["should_handoff"] is True
    assert result["next_check"]["risk_level"] == "critical"
    assert "断电" in result["next_check"]["action"]


def test_completed_low_confidence_path_hands_off():
    observations = [
        {"check_id": check_id, "outcome": "unknown"}
        for check_id in (
            "debug_led", "memory_reseat", "display_path", "cpu_power", "clear_cmos"
        )
    ]
    result = AdaptiveDiagnosisService().next_check(
        "黑屏", "no_display", observations
    )

    assert result["status"] == "complete"
    assert result["next_check"] is None
    assert result["should_handoff"] is True
    assert result["stop_reason"] == "all_checks_completed"


def test_adaptive_diagnosis_is_exposed_in_openapi():
    from app.main import app

    assert "/api/agent/diagnosis/next-check" in app.openapi()["paths"]
