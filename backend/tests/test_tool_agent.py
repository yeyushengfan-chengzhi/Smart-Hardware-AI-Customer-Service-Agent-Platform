from fastapi.testclient import TestClient

from app.agents.tool_agent import ToolAgent
from app.main import app
from app.tools.hardware_tools import compatibility_check_tool, hardware_spec_tool


client = TestClient(app)


def test_hardware_spec_tool_returns_b850_specification():
    result = hardware_spec_tool("B850")
    assert result["socket"] == "AM5"
    assert result["memory_type"] == "DDR5"
    assert result["source_file"]
    assert result["source_page"] == 17


def test_unknown_compatibility_is_not_reported_as_incompatible():
    result = compatibility_check_tool("13700K", "B850")
    assert result["compatible"] == "unknown"
    assert result["source_file"]


def test_tool_agent_extracts_entities_without_rag():
    result = ToolAgent().run("9700X可以搭配B850主板吗")
    assert result["tool_input"] == {"cpu": "Ryzen 7 9700X", "motherboard": "B850"}
    assert result["tool_result"]["compatible"] == "yes"


def test_b850_spec_endpoint():
    response = client.post("/api/agent/tool", json={"query": "B850主板的规格是什么"})
    assert response.status_code == 200
    assert response.json()["tool_name"] == "hardware_spec_tool"
    assert response.json()["tool_result"]["memory_type"] == "DDR5"
    assert response.json()["tool_result"]["socket"] == "AM5"
    assert response.json()["tool_result"]["source_file"]


def test_compatibility_endpoint():
    response = client.post("/api/agent/tool", json={"query": "9700X可以搭配B850主板吗"})
    assert response.status_code == 200
    assert response.json()["tool_name"] == "pc_build_compatibility_tool"
    assert response.json()["tool_result"]["compatible"] == "yes"


def test_socket_conflict_endpoint_reports_incompatible():
    response = client.post("/api/agent/tool", json={"query": "13700K可以搭配B850吗"})
    assert response.status_code == 200
    assert response.json()["tool_name"] == "pc_build_compatibility_tool"
    assert response.json()["tool_result"]["compatible"] == "no"


def test_unknown_cpu_compatibility_routes_to_tool():
    response = client.post("/api/agent/route", json={"query": "13700K可以搭配B850主板吗"})
    assert response.status_code == 200
    assert response.json()["intent"] == "compatibility_check"
    assert response.json()["route"] == "tool"


def test_compatibility_query_routes_to_tool():
    response = client.post("/api/agent/route", json={"query": "9700X可以搭配B850主板吗"})
    assert response.status_code == 200
    assert response.json()["route"] == "tool"


def test_gpu_detection_problem_still_routes_to_diagnosis():
    response = client.post("/api/agent/route", json={"query": "我的显卡无法检测怎么办"})
    assert response.status_code == 200
    assert response.json()["route"] == "diagnosis"


def test_b850_ddr5_query_never_routes_to_general_agent():
    response = client.post("/api/agent/route", json={"query": "B850主板支持DDR5吗"})
    assert response.status_code == 200
    assert response.json()["route"] in {"knowledge", "tool"}
