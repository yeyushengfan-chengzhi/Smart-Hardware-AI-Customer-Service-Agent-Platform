from app.agents.diagnosis_agent import DiagnosisAgent
from app.routers import agent as agent_router
from app.schemas import AgentRouteRequest, DiagnosisRequest


class FakeRAGService:
    def __init__(self):
        self.queries = []

    def search(self, query, top_k):
        self.queries.append((query, top_k))
        return [{
            "filename": "manual.pdf", "page_number": 12, "section_title": "Troubleshooting",
            "chunk_id": 1, "document_id": 1, "content": "content", "score": .9,
            "semantic_score": .9, "keyword_score": .9,
        }]


def actions(result):
    return " ".join(step["action"] for step in result["steps"])


def test_motherboard_no_display_has_required_diagnosis_steps_and_sources():
    rag = FakeRAGService()
    result = DiagnosisAgent(rag).diagnose("我的主板开机没有显示怎么办")
    assert result["device"] == "motherboard"
    assert result["fault_type"] == "no_display"
    assert all(word in actions(result) for word in ("EZ Debug LED", "CPU", "DRAM", "GPU", "CMOS"))
    assert all(step["sources"][0]["filename"] == "manual.pdf" for step in result["steps"])
    assert len(rag.queries) == len(result["steps"])


def test_gpu_not_detected_has_pcie_detection_and_output_steps():
    result = DiagnosisAgent(FakeRAGService()).diagnose("显卡无法检测怎么办")
    assert result["device"] == "gpu"
    assert result["fault_type"] == "installation_error"
    assert all(word in actions(result) for word in ("PCIe", "GPU", "显示输出"))


def test_memory_fault_light_has_dram_and_dimm_steps():
    result = DiagnosisAgent(FakeRAGService()).diagnose("内存故障灯亮怎么办")
    assert result["device"] == "memory"
    assert all(word in actions(result) for word in ("DRAM", "DIMM"))


def test_gpu_query_routes_and_executes_diagnosis(monkeypatch):
    query = "我的显卡无法检测怎么办"
    captured = {}

    def fake_diagnose(query, device_type, fault_type):
        captured.update(query=query, device_type=device_type, fault_type=fault_type)
        return {
            "query": query,
            "device": device_type,
            "fault_type": fault_type,
            "steps": [{"action": "检查 PCIe", "reason": "确认连接", "sources": []}],
        }

    monkeypatch.setattr(agent_router.diagnosis_agent, "diagnose", fake_diagnose)

    route_response = agent_router.route_query(AgentRouteRequest(query=query))
    diagnosis_response = agent_router.diagnose_hardware(DiagnosisRequest(query=query))

    assert route_response.route == "diagnosis"
    assert diagnosis_response.device == "gpu"
    assert diagnosis_response.fault_type == "hardware_error"
    assert diagnosis_response.steps
    assert captured == {
        "query": query,
        "device_type": "gpu",
        "fault_type": "hardware_error",
    }


def test_diagnosis_is_exposed_in_openapi():
    from app.main import app
    assert "/api/agent/diagnosis" in app.openapi()["paths"]
