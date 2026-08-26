import pytest

from app.agents.supervisor_agent import SupervisorAgent
from app.agents.tool_agent import ToolAgent
from app.tools.pc_build_tools import pc_build_compatibility_tool


def test_cpu_and_motherboard_socket_match():
    result = pc_build_compatibility_tool(cpu="Ryzen 7 9700X", motherboard="B850")
    assert result["compatible"] == "yes"
    assert result["risk_level"] == "low"
    assert any(item["rule"] == "cpu_motherboard_socket" for item in result["checked_items"])


def test_cpu_and_motherboard_socket_conflict():
    result = pc_build_compatibility_tool(cpu="Intel Core i7-13700K", motherboard="B850")
    assert result["compatible"] == "no"
    assert result["risk_level"] == "high"
    assert any("LGA1700" in reason and "AM5" in reason for reason in result["hard_conflicts"])


def test_matx_board_in_atx_case_is_warning_not_conflict():
    result = pc_build_compatibility_tool(motherboard="B850M", case="ATX标准机箱")
    assert result["compatible"] == "warning"
    assert not result["hard_conflicts"]
    assert result["warning_types"] == ["aesthetic"]
    assert any("下方空间较空" in warning for warning in result["warnings"])
    assert not any("走线" in suggestion for suggestion in result["suggestions"])


def test_gpu_longer_than_case_is_hard_conflict():
    result = pc_build_compatibility_tool(
        gpu="340mm显卡",
        case="最大支持330mm显卡的机箱",
    )
    assert result["compatible"] == "no"
    assert any("超出 10mm" in reason for reason in result["hard_conflicts"])


def test_thick_gpu_and_bottom_fans_are_warning():
    result = pc_build_compatibility_tool(gpu="3.5槽显卡", case="ATX标准机箱")
    assert result["compatible"] == "warning"
    assert result["warning_types"] == ["clearance"]
    assert any("底部风扇" in warning for warning in result["warnings"])


def test_dual_tower_cooler_and_tall_memory_are_warning():
    result = pc_build_compatibility_tool(
        cpu_cooler="双塔风冷",
        memory="DDR5高马甲内存",
    )
    assert result["compatible"] == "warning"
    assert any("高马甲内存" in warning for warning in result["warnings"])


def test_psu_far_below_gpu_recommendation_is_high_risk():
    result = pc_build_compatibility_tool(gpu="RTX 4090", psu="650W ATX电源")
    assert result["compatible"] == "no"
    assert result["risk_level"] == "high"
    assert any("低 200W" in reason for reason in result["hard_conflicts"])


def test_missing_parts_returns_unknown_without_guessing():
    result = pc_build_compatibility_tool()
    assert result["compatible"] == "unknown"
    assert result["risk_level"] == "unknown"
    assert result["warning_types"] == ["data_missing"]
    assert result["hard_conflicts"] == []
    assert result["suggestions"]


def test_complete_known_build_checks_all_available_pairs():
    result = pc_build_compatibility_tool(
        cpu="Ryzen 7 9700X",
        motherboard="B850",
        case="ATX标准机箱",
        gpu="RTX 4070 SUPER",
        cpu_cooler="155mm塔式风冷",
        memory="DDR5标准内存",
        psu="650W ATX电源",
    )
    assert result["compatible"] == "yes"
    assert len(result["checked_items"]) >= 7


@pytest.mark.parametrize(
    "query",
    [
        "Ryzen 7 9700X 可以搭配 B850 主板吗？",
        "i7-13700K 可以搭配 B850 主板吗？",
        "M-ATX 主板装 ATX 机箱可以吗，会不会不好看？",
        "340mm 显卡能不能装进最大支持 330mm 显卡的机箱？",
        "3.5 槽显卡会不会挡底部风扇？",
        "双塔风冷会不会挡高马甲内存？",
        "这套配置兼容吗？",
        "我不知道具体型号，能不能帮我看看这套配置？",
        "电源瓦数够不够？",
    ],
)
def test_pc_build_questions_route_to_tool_agent(query):
    routing = SupervisorAgent().route(query)
    assert routing["intent"] == "compatibility_check"
    assert routing["route"] == "tool"
    response = ToolAgent().run(query)
    assert response["tool_name"] == "pc_build_compatibility_tool"
    assert {
        "compatible",
        "risk_level",
        "hard_conflicts",
        "warnings",
        "warning_types",
        "warning_details",
        "suggestions",
        "checked_items",
        "primary_check",
        "primary_warning",
    }.issubset(response["tool_result"])
    assert "missing_info" in response["tool_result"]


def test_tool_agent_explains_result_for_beginners():
    response = ToolAgent().run("i7-13700K 可以搭配 B850 主板吗？")
    assert "结论：" in response["answer"]
    assert "不兼容原因：" in response["answer"]
    assert "小白更稳的选择：" in response["answer"]


def test_aesthetic_warning_has_specific_beginner_answer():
    response = ToolAgent().run("M-ATX 主板装 ATX 机箱可以吗，会不会不好看？")
    assert response["tool_result"]["warning_types"] == ["aesthetic"]
    assert "可以正常安装，物理兼容" in response["answer"]
    assert "走线、风扇和安装公差" not in response["answer"]


def test_power_warning_is_classified_separately():
    result = pc_build_compatibility_tool(gpu="RTX 4070 SUPER", psu="600W ATX电源")
    assert result["compatible"] == "warning"
    assert result["warning_types"] == ["power"]


def test_unknown_model_is_data_missing():
    result = pc_build_compatibility_tool(cpu="不知道具体型号", motherboard="B850")
    assert result["compatible"] == "unknown"
    assert "data_missing" in result["warning_types"]


def test_bottom_fan_question_prioritizes_thickness_warning():
    response = ToolAgent().run("3.5 槽显卡会不会挡底部风扇？")
    result = response["tool_result"]
    assert result["primary_check"] == "gpu_bottom_fan_risk"
    assert result["primary_warning"]["rule"] == "gpu_bottom_fan_risk"
    lines = response["answer"].splitlines()
    assert "厚显卡" in lines[0] and "底部进风" in lines[0]
    assert "重点回答：" in response["answer"]
    assert "另外还需注意：" in response["answer"]
    assert response["answer"].index("底部进风") < response["answer"].index("长度上限")


def test_gpu_length_question_prioritizes_length_check():
    response = ToolAgent().run("3.5 槽显卡会不会太长，能装进 ATX 机箱吗？")
    result = response["tool_result"]
    assert result["primary_check"] == "gpu_length_clearance"
    assert result["primary_warning"]["rule"] == "gpu_length_clearance"
    assert "显卡长度接近机箱上限" in response["answer"].splitlines()[0]


def test_overall_build_question_keeps_combined_warning_view():
    response = ToolAgent().run("这套配置兼容吗？")
    assert response["tool_result"]["primary_check"] == "overall_compatibility"
    assert "重点回答：" not in response["answer"]


@pytest.mark.parametrize(
    "query",
    [
        "这个机箱能装360水冷吗？",
        "360水冷装前面会不会挡显卡？",
        "顶部装水冷会不会顶内存？",
        "前置冷排会不会影响显卡长度？",
        "这个风冷会不会超高？",
        "双塔风冷会不会挡高马甲内存？",
        "海景房机箱适合水冷还是风冷？",
        "水冷装顶部好还是前面好？",
    ],
)
def test_cooling_questions_route_to_compatibility_tool(query):
    routing = SupervisorAgent().route(query)
    assert routing["intent"] == "compatibility_check"
    response = ToolAgent().run(query)
    assert response["tool_name"] == "pc_build_compatibility_tool"
    assert response["tool_result"]["compatible"] in {"yes", "warning", "no", "unknown"}


def test_unsupported_radiator_size_is_hard_conflict():
    result = pc_build_compatibility_tool(
        case="M-ATX紧凑机箱",
        aio_cooler="360mm一体水冷",
    )
    assert result["compatible"] == "no"
    assert any(item["rule"] == "radiator_case_support" for item in result["checked_items"])


def test_front_radiator_gpu_limit_missing_is_unknown():
    result = pc_build_compatibility_tool(
        case="ATX标准机箱",
        gpu="RTX 4090",
        aio_cooler="360mm一体水冷",
        radiator_position="front",
        check_mode="front_radiator_gpu_clearance",
    )
    assert result["compatible"] == "unknown"
    assert "case.max_gpu_length_with_front_radiator_mm" in result["missing_info"]


def test_top_radiator_reports_clearance_risk():
    result = pc_build_compatibility_tool(
        case="长显卡展示机箱",
        aio_cooler="360mm一体水冷",
        radiator_position="top",
    )
    assert any(item["rule"] == "top_radiator_clearance" for item in result["warning_details"])


def test_air_cooler_height_conflict_and_tight_clearance():
    conflict = pc_build_compatibility_tool(
        case="M-ATX紧凑机箱",
        cpu_cooler="双塔风冷",
    )
    tight = pc_build_compatibility_tool(
        case="M-ATX紧凑机箱",
        cpu_cooler="155mm塔式风冷",
    )
    assert conflict["compatible"] == "no"
    assert tight["compatible"] == "warning"
    assert any(item["rule"] == "cooler_case_height" for item in tight["warning_details"])


def test_missing_case_and_radiator_size_are_reported():
    missing_case = pc_build_compatibility_tool(aio_cooler="360mm一体水冷")
    missing_size = ToolAgent().run("这个机箱能装水冷吗，但我没说冷排尺寸")["tool_result"]
    assert "case" in missing_case["missing_info"]
    assert "aio_cooler" in missing_size["missing_info"]
