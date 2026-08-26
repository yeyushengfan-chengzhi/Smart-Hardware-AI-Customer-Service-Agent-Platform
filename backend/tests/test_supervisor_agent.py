import pytest

from app.agents.supervisor_agent import SupervisorAgent
from app.routers.agent import route_query
from app.schemas import AgentRouteRequest


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        (
            "我的主板开机没有显示怎么办",
            ("fault_diagnosis", "motherboard", "no_display", "diagnosis"),
        ),
        (
            "B850支持什么CPU",
            ("product_info", "motherboard", "unknown", "knowledge"),
        ),
        (
            "怎么申请售后",
            ("after_sales", "unknown", "unknown", "AfterSalesAgent"),
        ),
        (
            "不知道怎么描述",
            ("unknown", "unknown", "unknown", "GeneralAgent"),
        ),
    ],
)
def test_supervisor_routes_required_queries(query, expected):
    result = SupervisorAgent().route(query)

    assert (
        result["intent"],
        result["device_type"],
        result["fault_type"],
        result["route"],
    ) == expected


def test_route_endpoint_includes_original_query():
    response = route_query(AgentRouteRequest(query="我的主板开机没有显示怎么办"))

    assert response.query == "我的主板开机没有显示怎么办"
    assert response.intent == "fault_diagnosis"
    assert response.route == "diagnosis"


@pytest.mark.parametrize(
    "query",
    [
        "我的显卡无法检测怎么办",
        "电脑找不到独立显卡",
        "GPU识别不到",
        "显卡没有输出",
        "插上显卡没有画面",
        "开机显示器无信号",
        "内存条检测不到",
        "主板无法启动",
    ],
)
def test_device_plus_problem_state_routes_to_diagnosis(query):
    result = SupervisorAgent().route(query)
    assert result["intent"] == "fault_diagnosis"
    assert result["route"] == "diagnosis"


def test_gpu_not_detected_preserves_device_classification():
    result = SupervisorAgent().route("我的显卡无法检测怎么办")
    assert result["device_type"] == "gpu"


@pytest.mark.parametrize(
    "query",
    [
        "9700X可以搭配B850主板吗",
        "13700K可以搭配B850主板吗",
        "i7-13700K和B850兼容吗",
        "Intel 13700K能不能用B850主板",
        "7800X3D可以用B850主板吗",
        "14700K可以用Z790主板吗",
        "7800X3D能搭配X670 motherboard吗",
        "9950X可以安装在B850上吗",
        "B850能用Ryzen 7 9700X吗",
        "9700X与B850是否匹配",
        "未知型号CPU可以搭配B850吗",
    ],
)
def test_cpu_motherboard_compatibility_queries_route_to_tool(query):
    result = SupervisorAgent().route(query)

    assert result["intent"] == "compatibility_check"
    assert result["device_type"] == "motherboard"
    assert result["route"] == "tool"


@pytest.mark.parametrize(
    "query",
    [
        "B850支持什么CPU",
        "B850主板支持DDR5吗",
        "B850支持PCIe 5.0吗",
        "这个主板有几个M.2接口",
        "显卡需要多少瓦电源",
        "B850支持什么内存",
        "B850主板网卡规格是什么",
        "B850主板的音频接口规格",
        "B850主板如何更新BIOS",
        "B850主板尺寸是什么",
    ],
)
def test_product_specification_queries_route_to_knowledge(query):
    result = SupervisorAgent().route(query)
    assert result["intent"] == "product_info"
    assert result["route"] == "knowledge"


def test_fault_semantics_still_take_priority_over_product_routing():
    result = SupervisorAgent().route("我的显卡无法检测怎么办")
    assert result["intent"] == "fault_diagnosis"
    assert result["route"] == "diagnosis"


@pytest.mark.parametrize(
    "query",
    [
        "电脑经常蓝屏怎么排查",
        "玩游戏时蓝屏重启",
        "BIOS里找不到固态硬盘",
        "新装的M.2硬盘无法识别",
        "机械硬盘在系统中不显示",
        "电脑只识别一根内存",
        "内存频率显示不正确怎么办",
        "电脑随机死机怎么排查",
        "显卡驱动安装失败怎么办",
    ],
)
def test_regression_fault_expressions_route_to_diagnosis(query):
    result = SupervisorAgent().route(query)
    assert result["intent"] == "fault_diagnosis"
    assert result["route"] == "diagnosis"


def test_product_cpu_support_query_never_routes_to_general_agent():
    result = SupervisorAgent().route("B850主板支持什么CPU")
    assert result["route"] in {"knowledge", "tool"}


def test_gpu_fault_is_not_misclassified_as_tool_call():
    result = SupervisorAgent().route("我的显卡无法检测怎么办")
    assert result["route"] == "diagnosis"


def test_unrelated_query_does_not_route_to_diagnosis():
    result = SupervisorAgent().route("今天天气怎么样")
    assert result["intent"] == "unknown"
    assert result["route"] == "GeneralAgent"


def test_unrelated_query_is_not_misclassified_as_tool_call():
    result = SupervisorAgent().route("今天天气怎么样")
    assert result["route"] == "GeneralAgent"


@pytest.mark.parametrize(
    "query",
    [
        "M-ATX 主板装 ATX 机箱会不会不好看？",
        "厚显卡会不会挡底部风扇？",
        "前置 360 冷排会不会影响显卡长度？",
        "顶部水冷会不会顶内存？",
        "双塔风冷会不会挡高马甲内存？",
        "小机箱装机走线难不难？",
        "海景房机箱风道要注意什么？",
    ],
)
def test_community_build_risk_queries_route_to_tool(query):
    result = SupervisorAgent().route(query)

    assert result["intent"] == "compatibility_check"
    assert result["route"] == "tool"


def test_route_is_exposed_in_openapi():
    from app.main import app

    operation = app.openapi()["paths"]["/api/agent/route"]["post"]

    assert operation["tags"] == ["agent"]
    assert "200" in operation["responses"]
