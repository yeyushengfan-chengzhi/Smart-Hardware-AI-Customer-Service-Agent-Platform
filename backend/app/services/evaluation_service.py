"""Synchronous, rule-based Agent evaluation service."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.supervisor_agent import supervisor_agent
from app.database import SessionLocal
from app.models.agent_trace import AgentTrace
from app.models.evaluation_case import EvaluationCase
from app.models.evaluation_result import EvaluationResult
from app.models.evaluation_run import EvaluationRun
from app.routers.agent import (
    answer_product_knowledge,
    call_hardware_tool,
    diagnose_hardware,
    route_query,
)
from app.schemas import AgentKnowledgeRequest, AgentRouteRequest, AgentToolRequest, DiagnosisRequest
from app.services.trace_service import save_trace_safely

PASS_THRESHOLD = 80.0


def _case(category: str, question: str, route: str, agent: str, keywords: list[str], tool: str = "") -> dict:
    return {"category": category, "question": question, "expected_route": route,
            "expected_agent": agent, "expected_keywords": keywords, "expected_tool": tool}


def _cooling_case(
    question: str,
    result_type: str,
    warning_type: str,
    keywords: list[str],
) -> dict:
    """Map Phase 7.3 expectations onto the existing EvaluationCase schema."""
    case_data = _case(
        "tool",
        question,
        "tool",
        "ToolAgent",
        keywords,
        "pc_build_compatibility_tool",
    )
    case_data["expected_answer"] = json.dumps(
        {
            "expected_result_type": result_type,
            "expected_warning_type": warning_type,
        },
        ensure_ascii=False,
    )
    return case_data


def _community_case(question: str, keywords: list[str]) -> dict:
    """Store Phase 7.4 source expectations without a database migration."""
    case_data = _case(
        "tool",
        question,
        "tool",
        "ToolAgent",
        keywords,
        "pc_build_compatibility_tool",
    )
    case_data["expected_answer"] = json.dumps(
        {"expected_source_type": "community_experience"},
        ensure_ascii=False,
    )
    return case_data


DEFAULT_CASES = [
    # Knowledge (20)
    _case("knowledge", "B850主板支持DDR5吗", "knowledge", "KnowledgeAgent", ["DDR5"]),
    _case("knowledge", "B850支持什么CPU", "knowledge", "KnowledgeAgent", ["CPU"]),
    _case("knowledge", "B850主板有哪些接口", "knowledge", "KnowledgeAgent", ["接口"]),
    _case("knowledge", "B850支持什么内存", "knowledge", "KnowledgeAgent", ["内存", "DDR5"]),
    _case("knowledge", "B850主板有几个M.2插槽", "knowledge", "KnowledgeAgent", ["M.2"]),
    _case("knowledge", "B850主板支持PCIe 5.0吗", "knowledge", "KnowledgeAgent", ["PCIe"]),
    _case("knowledge", "B850主板的CPU插槽是什么", "knowledge", "KnowledgeAgent", ["插槽"]),
    _case("knowledge", "B850可以使用9700X处理器吗", "knowledge", "KnowledgeAgent", ["9700X"]),
    _case("knowledge", "B850主板最高支持多大内存", "knowledge", "KnowledgeAgent", ["内存"]),
    _case("knowledge", "B850主板支持双通道内存吗", "knowledge", "KnowledgeAgent", ["双通道"]),
    _case("knowledge", "B850主板后置USB接口有哪些", "knowledge", "KnowledgeAgent", ["USB"]),
    _case("knowledge", "B850主板有没有Type-C接口", "knowledge", "KnowledgeAgent", ["Type-C"]),
    _case("knowledge", "B850主板网卡规格是什么", "knowledge", "KnowledgeAgent", ["网卡"]),
    _case("knowledge", "B850主板支持WiFi 6E吗", "knowledge", "KnowledgeAgent", ["WiFi"]),
    _case("knowledge", "B850主板如何进入BIOS", "knowledge", "KnowledgeAgent", ["BIOS"]),
    _case("knowledge", "B850主板如何更新BIOS", "knowledge", "KnowledgeAgent", ["BIOS"]),
    _case("knowledge", "B850主板支持哪些存储接口", "knowledge", "KnowledgeAgent", ["存储"]),
    _case("knowledge", "B850主板的音频接口规格", "knowledge", "KnowledgeAgent", ["音频"]),
    _case("knowledge", "B850主板尺寸是什么", "knowledge", "KnowledgeAgent", ["尺寸"]),
    _case("knowledge", "B850主板供电接口在哪里", "knowledge", "KnowledgeAgent", ["供电"]),
    # Diagnosis (15)
    _case("diagnosis", "我的显卡无法检测怎么办", "diagnosis", "DiagnosisAgent", ["供电", "驱动", "检测"]),
    _case("diagnosis", "电脑找不到独立显卡", "diagnosis", "DiagnosisAgent", ["显卡", "供电"]),
    _case("diagnosis", "电脑开机没有显示怎么办", "diagnosis", "DiagnosisAgent", ["检查"]),
    _case("diagnosis", "安装新显卡后显示器黑屏", "diagnosis", "DiagnosisAgent", ["显卡"]),
    _case("diagnosis", "电脑经常蓝屏怎么排查", "diagnosis", "DiagnosisAgent", ["蓝屏"]),
    _case("diagnosis", "玩游戏时蓝屏重启", "diagnosis", "DiagnosisAgent", ["检查"]),
    _case("diagnosis", "BIOS里找不到固态硬盘", "diagnosis", "DiagnosisAgent", ["硬盘"]),
    _case("diagnosis", "新装的M.2硬盘无法识别", "diagnosis", "DiagnosisAgent", ["M.2"]),
    _case("diagnosis", "机械硬盘在系统中不显示", "diagnosis", "DiagnosisAgent", ["硬盘"]),
    _case("diagnosis", "电脑只识别一根内存", "diagnosis", "DiagnosisAgent", ["内存"]),
    _case("diagnosis", "内存频率显示不正确怎么办", "diagnosis", "DiagnosisAgent", ["内存"]),
    _case("diagnosis", "开启EXPO后无法开机", "diagnosis", "DiagnosisAgent", ["内存"]),
    _case("diagnosis", "电脑随机死机怎么排查", "diagnosis", "DiagnosisAgent", ["检查"]),
    _case("diagnosis", "开机风扇转但是没有画面", "diagnosis", "DiagnosisAgent", ["检查"]),
    _case("diagnosis", "显卡驱动安装失败怎么办", "diagnosis", "DiagnosisAgent", ["驱动"]),
    # Tool (18)
    _case("tool", "9700X可以搭配B850主板吗", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("tool", "9600X和B850兼容吗", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("tool", "9950X可以安装在B850上吗", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("tool", "B850能用Ryzen 7 9700X吗", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("tool", "9700X与B850是否匹配", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("tool", "查询B850主板规格", "tool", "ToolAgent", ["DDR5"], "hardware_spec_tool"),
    _case("tool", "B850的内存类型和插槽规格", "tool", "ToolAgent", ["DDR5"], "hardware_spec_tool"),
    _case("tool", "请用规格工具查看B850主板", "tool", "ToolAgent", ["B850"], "hardware_spec_tool"),
    _case("tool", "B850硬件规格是什么", "tool", "ToolAgent", ["DDR5"], "hardware_spec_tool"),
    _case("tool", "帮我查一下B850支持的插槽", "tool", "ToolAgent", ["AM5"], "hardware_spec_tool"),
    _case("tool", "Ryzen 7 9700X 可以搭配 B850 主板吗？", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("tool", "i7-13700K 可以搭配 B850 主板吗？", "tool", "ToolAgent", ["不兼容"], "pc_build_compatibility_tool"),
    _case("tool", "M-ATX 主板装 ATX 机箱可以吗，会不会不好看？", "tool", "ToolAgent", ["下方留空"], "pc_build_compatibility_tool"),
    _case("tool", "340mm 显卡能不能装进最大支持 330mm 显卡的机箱？", "tool", "ToolAgent", ["超过"], "pc_build_compatibility_tool"),
    _case("tool", "3.5 槽显卡会不会挡底部风扇？", "tool", "ToolAgent", ["底部风扇"], "pc_build_compatibility_tool"),
    _case("tool", "双塔风冷会不会挡高马甲内存？", "tool", "ToolAgent", ["高马甲内存"], "pc_build_compatibility_tool"),
    _case("tool", "这套配置兼容吗？", "tool", "ToolAgent", ["信息不足"], "pc_build_compatibility_tool"),
    _case("tool", "电源瓦数够不够？", "tool", "ToolAgent", ["信息不足"], "pc_build_compatibility_tool"),
    # Cooling compatibility (10)
    _cooling_case("这个机箱能装360水冷吗？", "unknown", "data_missing", ["机箱型号"]),
    _cooling_case("360水冷装前面会不会挡显卡？", "unknown", "data_missing", ["显卡"]),
    _cooling_case("顶部装360水冷会不会顶内存？", "unknown", "clearance", ["顶部冷排"]),
    _cooling_case("双塔风冷装进M-ATX紧凑机箱会不会超高？", "no", "clearance", ["超过机箱限高"]),
    _cooling_case("155mm塔式风冷装M-ATX紧凑机箱余量够吗？", "warning", "clearance", ["只剩"]),
    _cooling_case("双塔风冷会不会挡DDR5高马甲内存？", "warning", "clearance", ["高马甲内存"]),
    _cooling_case("没说机箱型号，能判断360水冷兼容吗？", "unknown", "data_missing", ["缺少机箱型号"]),
    _cooling_case("这个机箱能装水冷吗，但我没说冷排尺寸", "unknown", "data_missing", ["水冷"]),
    _cooling_case("海景房机箱适合水冷还是风冷？", "unknown", "data_missing", ["完整品牌型号"]),
    _cooling_case("M-ATX紧凑机箱支持360mm一体水冷吗？", "no", "placement", ["不支持"]),
    # Community experience (5)
    _community_case(
        "M-ATX 主板装 ATX 机箱会不会不好看？",
        ["M-ATX", "ATX", "观感", "空间"],
    ),
    _community_case(
        "厚显卡会不会挡底部风扇？",
        ["厚显卡", "底部风扇", "空间风险"],
    ),
    _community_case(
        "前置 360 冷排会不会影响显卡长度？",
        ["前置冷排", "显卡长度", "空间"],
    ),
    _community_case(
        "顶部水冷会不会顶内存？",
        ["顶部水冷", "内存", "VRM", "空间"],
    ),
    _community_case(
        "双塔风冷会不会挡高马甲内存？",
        ["双塔风冷", "高马甲内存", "避让"],
    ),
    # General (5)
    _case("general", "今天天气怎么样", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
    _case("general", "给我讲一个笑话", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
    _case("general", "你是谁", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
    _case("general", "帮我写一首诗", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
    _case("general", "附近有什么餐厅", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
    # Handoff (5)
    _case("handoff", "13700K可以搭配B850主板吗", "tool", "ToolAgent", ["兼容"], "pc_build_compatibility_tool"),
    _case("handoff", "未知型号CPU可以搭配B850吗", "tool", "ToolAgent", ["无法"], "pc_build_compatibility_tool"),
    _case("handoff", "查一下不存在型号主板XYZ的规格", "knowledge", "KnowledgeAgent", [], ""),
    _case("handoff", "这个问题没有资料时请转人工", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
    _case("handoff", "我要人工客服", "GeneralAgent", "GeneralAgent", ["智能硬件"]),
]


def seed_default_cases(db: Session) -> int:
    """Insert the regression suite idempotently while preserving user-defined variants."""
    existing_rows = list(db.scalars(select(EvaluationCase)).all())
    defaults = {(case["question"], case["expected_route"], case["expected_agent"], case.get("expected_tool", "")): case for case in DEFAULT_CASES}
    for row in existing_rows:
        replacement_key = (
            row.question,
            row.expected_route,
            row.expected_agent,
            "pc_build_compatibility_tool",
        )
        if row.expected_tool == "compatibility_check_tool" and replacement_key in defaults:
            row.expected_tool = "pc_build_compatibility_tool"
    existing = {(row.question, row.expected_route, row.expected_agent, row.expected_tool) for row in existing_rows}
    for row in existing_rows:
        key = (row.question, row.expected_route, row.expected_agent, row.expected_tool)
        if key in defaults:
            default = defaults[key]
            row.category = default["category"]
            if _expected_source_type(default.get("expected_answer", "")):
                row.expected_answer = default["expected_answer"]
                row.expected_keywords = default["expected_keywords"]
    additions = [EvaluationCase(**case) for key, case in defaults.items() if key not in existing]
    db.add_all(additions)
    db.commit()
    return len(additions)


def execute_evaluation(db: Session, run_name: str) -> EvaluationRun:
    cases = list(db.scalars(select(EvaluationCase).order_by(EvaluationCase.id)).all())
    run = EvaluationRun(run_name=run_name, total_cases=len(cases))
    db.add(run)
    db.flush()

    for case in cases:
        result = _evaluate_case(case, run.id)
        db.add(result)

    db.flush()
    results = list(db.scalars(select(EvaluationResult).where(EvaluationResult.run_id == run.id)).all())
    run.passed_cases = sum(item.status == "passed" for item in results)
    run.failed_cases = run.total_cases - run.passed_cases
    run.pass_rate = round(run.passed_cases / run.total_cases, 4) if run.total_cases else 0.0
    db.commit()
    db.refresh(run)
    return run


def _evaluate_case(case: EvaluationCase, run_id: int) -> EvaluationResult:
    trace = None
    execution_error = ""
    try:
        trace_id = _execute_agent(case.question)
        trace = _load_trace(trace_id)
        if trace is None:
            raise RuntimeError(f"Trace {trace_id} was not persisted")
    except Exception as exc:
        execution_error = str(exc)
        trace = _latest_trace(case.question)
        if trace is None:
            trace_id = _save_evaluation_failure_trace(case.question, execution_error)
            trace = _load_trace(trace_id)

    actual_route = trace.route if trace else ""
    actual_agent = trace.agent_name if trace else ""
    actual_tool = trace.tool_name if trace else ""
    route_match = actual_route == case.expected_route
    agent_match = actual_agent == case.expected_agent
    keyword_score = _keyword_score(case.expected_keywords, trace)
    tool_match = not case.expected_tool or actual_tool == case.expected_tool
    expected_source_type = _expected_source_type(case.expected_answer)
    source_type_match = (
        not expected_source_type
        or (
            trace is not None
            and any(
                source.get("source_type") == expected_source_type
                for source in (trace.sources_json or [])
            )
        )
    )
    final_score = round((40 if route_match else 0) + (30 if agent_match else 0)
                        + (20 if tool_match else 0) + 10 * keyword_score, 2)
    errors = []
    if execution_error:
        errors.append(execution_error)
    if not route_match:
        errors.append(f"route mismatch: expected {case.expected_route}, got {actual_route or 'none'}")
    if not agent_match:
        errors.append(f"agent mismatch: expected {case.expected_agent}, got {actual_agent or 'none'}")
    if keyword_score < 1:
        errors.append("expected keywords were not fully matched")
    if not tool_match:
        errors.append(f"tool mismatch: expected {case.expected_tool}, got {actual_tool or 'none'}")
    if not source_type_match:
        errors.append(
            f"source type mismatch: expected {expected_source_type}, got none"
        )
    passed = (
        not execution_error
        and final_score >= PASS_THRESHOLD
        and source_type_match
    )
    return EvaluationResult(
        run_id=run_id, case_id=case.id, trace_id=trace.trace_id if trace else "",
        question=case.question, actual_route=actual_route, expected_route=case.expected_route,
        route_match=route_match, actual_agent=actual_agent, expected_agent=case.expected_agent,
        agent_match=agent_match, expected_tool=case.expected_tool, actual_tool=actual_tool,
        keyword_score=keyword_score, tool_match=tool_match,
        final_score=final_score, status="passed" if passed else "failed",
        error_message="; ".join(errors),
    )


def _execute_agent(question: str) -> str:
    routing = supervisor_agent.route(question)
    route = routing["route"]
    if route == "knowledge":
        response = answer_product_knowledge(AgentKnowledgeRequest(query=question))
    elif route == "diagnosis":
        response = diagnose_hardware(DiagnosisRequest(query=question))
    elif route == "tool":
        response = call_hardware_tool(AgentToolRequest(query=question))
    else:
        response = route_query(AgentRouteRequest(query=question))
    if not response.trace_id:
        raise RuntimeError("Agent execution did not return a trace_id")
    return response.trace_id


def _load_trace(trace_id: str) -> AgentTrace | None:
    with SessionLocal() as trace_db:
        return trace_db.scalar(select(AgentTrace).where(AgentTrace.trace_id == trace_id))


def _latest_trace(question: str) -> AgentTrace | None:
    with SessionLocal() as trace_db:
        return trace_db.scalar(
            select(AgentTrace).where(AgentTrace.query == question)
            .order_by(AgentTrace.created_time.desc(), AgentTrace.id.desc()).limit(1)
        )


def _save_evaluation_failure_trace(question: str, error: str) -> str:
    return save_trace_safely(
        query=question, route="unknown", intent="evaluation_error", device_type="unknown",
        fault_type="unknown", agent_name="GeneralAgent", final_answer="", sources_json=[],
        tool_name="", tool_input_json={}, tool_result_json={}, route_response_json={},
        agent_response_json={}, latency_json={}, handoff_suggested=True,
        handoff_reason="agent_failed", status="failed", error_message=error,
    )


def _keyword_score(expected_keywords: list, trace: AgentTrace | None) -> float:
    if not expected_keywords:
        return 1.0
    if trace is None:
        return 0.0
    content = "\n".join([
        trace.final_answer or "",
        json.dumps(trace.agent_response_json or {}, ensure_ascii=False),
    ]).casefold()
    matches = sum(str(keyword).casefold() in content for keyword in expected_keywords)
    return round(matches / len(expected_keywords), 4)


def _expected_source_type(expected_answer: str) -> str:
    if not expected_answer:
        return ""
    try:
        payload = json.loads(expected_answer)
    except (json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(payload, dict):
        return ""
    value = payload.get("expected_source_type")
    return value.strip() if isinstance(value, str) else ""
