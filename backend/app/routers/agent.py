"""SupervisorAgent routing endpoint."""

from time import perf_counter

from fastapi import APIRouter, HTTPException, status

from app.agents.diagnosis_agent import diagnosis_agent
from app.agents.knowledge_agent import knowledge_agent
from app.agents.supervisor_agent import supervisor_agent
from app.agents.tool_agent import tool_agent
from app.schemas import (
    AgentKnowledgeRequest,
    AgentKnowledgeResponse,
    AgentRouteRequest,
    AgentRouteResponse,
    AgentToolRequest,
    AgentToolResponse,
    DiagnosisRequest,
    DiagnosisResponse,
)
from app.services.llm_service import LLMServiceError
from app.services.trace_service import save_trace_safely


router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/route", response_model=AgentRouteResponse)
def route_query(payload: AgentRouteRequest) -> AgentRouteResponse:
    """Classify a question and return its destination without executing an agent."""
    result = supervisor_agent.route(payload.query)
    trace_id = None
    if result["route"] in {"GeneralAgent", "unknown"}:
        route_response = {"query": payload.query, **result}
        trace_id = save_trace_safely(
            query=payload.query, route=result["route"], intent=result["intent"],
            device_type=result["device_type"], fault_type=result["fault_type"],
            agent_name="GeneralAgent", final_answer="当前系统主要支持智能硬件客服问题。",
            sources_json=[], tool_name="", tool_input_json={}, tool_result_json={},
            route_response_json=route_response, agent_response_json={}, latency_json={},
            handoff_suggested=True, handoff_reason="route_unknown", status="success", error_message="",
        )
    return AgentRouteResponse(query=payload.query, trace_id=trace_id, **result)


@router.post("/tool", response_model=AgentToolResponse)
def call_hardware_tool(payload: AgentToolRequest) -> AgentToolResponse:
    """Execute a supported local structured hardware tool."""
    started = perf_counter()
    route_started = perf_counter()
    routing = supervisor_agent.route(payload.query)
    route_latency = round((perf_counter() - route_started) * 1000)
    try:
        agent_started = perf_counter()
        result = tool_agent.run(payload.query)
        agent_latency = round((perf_counter() - agent_started) * 1000)
        latency = _latency(route_latency, agent_latency, started)
        unknown = result["tool_result"].get("compatible") == "unknown"
        trace_id = _save_agent_trace(payload.query, routing, "ToolAgent", result, latency,
                                     handoff_reason="tool_unknown" if unknown else "")
        return AgentToolResponse(trace_id=trace_id, **result)
    except Exception as exc:
        _save_failed_trace(payload.query, routing, "ToolAgent", exc, started, route_latency)
        raise


@router.post("/diagnosis", response_model=DiagnosisResponse)
def diagnose_hardware(payload: DiagnosisRequest) -> DiagnosisResponse:
    """Execute DiagnosisAgent using the Supervisor classification as context."""
    started = perf_counter()
    route_started = perf_counter()
    routing = supervisor_agent.route(payload.query)
    route_latency = round((perf_counter() - route_started) * 1000)
    try:
        agent_started = perf_counter()
        result = diagnosis_agent.diagnose(payload.query, device_type=routing["device_type"], fault_type=routing["fault_type"])
        latency = _latency(route_latency, round((perf_counter() - agent_started) * 1000), started)
        result["answer"] = f"已生成 {len(result['steps'])} 个硬件故障排查步骤。"
        trace_id = _save_agent_trace(payload.query, routing, "DiagnosisAgent", result, latency)
        result.pop("answer")
        return DiagnosisResponse(trace_id=trace_id, **result)
    except Exception as exc:
        _save_failed_trace(payload.query, routing, "DiagnosisAgent", exc, started, route_latency)
        raise


@router.post("/knowledge", response_model=AgentKnowledgeResponse)
def answer_product_knowledge(payload: AgentKnowledgeRequest) -> AgentKnowledgeResponse:
    """Answer only product-knowledge questions selected by SupervisorAgent."""
    started = perf_counter()
    route_started = perf_counter()
    routing = supervisor_agent.route(payload.query)
    route_latency = round((perf_counter() - route_started) * 1000)
    if routing["intent"] != "product_info":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Query should be handled by route: {routing['route']}",
        )
    try:
        agent_started = perf_counter()
        result = knowledge_agent.answer(payload.query, top_k=payload.top_k)
        latency = _latency(route_latency, round((perf_counter() - agent_started) * 1000), started)
        trace_id = _save_agent_trace(
            payload.query, routing, "KnowledgeAgent", result, latency,
            handoff_reason="no_sources" if not result["sources"] else "",
        )
    except LLMServiceError as exc:
        _save_failed_trace(payload.query, routing, "KnowledgeAgent", exc, started, route_latency)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        _save_failed_trace(payload.query, routing, "KnowledgeAgent", exc, started, route_latency)
        raise
    return AgentKnowledgeResponse(trace_id=trace_id, **result)


def _latency(route_ms: int, agent_ms: int, started: float) -> dict[str, int]:
    return {"route_latency_ms": route_ms, "agent_latency_ms": agent_ms,
            "total_latency_ms": round((perf_counter() - started) * 1000)}


def _merged_sources(result: dict) -> list[dict]:
    sources = result.get("sources", []) or [source for step in result.get("steps", []) for source in step.get("sources", [])]
    seen = set()
    unique = []
    for source in sources:
        key = (source.get("filename"), source.get("page_number"), source.get("section_title"))
        if key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def _save_agent_trace(query: str, routing: dict, agent_name: str, result: dict,
                      latency: dict, handoff_reason: str = "") -> str:
    route_response = {"query": query, **routing}
    return save_trace_safely(
        query=query, route=routing["route"], intent=routing["intent"],
        device_type=routing["device_type"], fault_type=routing["fault_type"], agent_name=agent_name,
        final_answer=result.get("answer", ""), sources_json=_merged_sources(result),
        tool_name=result.get("tool_name") or "", tool_input_json=result.get("tool_input", {}),
        tool_result_json=result.get("tool_result", {}), route_response_json=route_response,
        agent_response_json=result, latency_json=latency, handoff_suggested=bool(handoff_reason),
        handoff_reason=handoff_reason, status="success", error_message="",
    )


def _save_failed_trace(query: str, routing: dict, agent_name: str, exc: Exception,
                       started: float, route_latency: int) -> str:
    return save_trace_safely(
        query=query, route=routing["route"], intent=routing["intent"],
        device_type=routing["device_type"], fault_type=routing["fault_type"], agent_name=agent_name,
        final_answer="", sources_json=[], tool_name="", tool_input_json={}, tool_result_json={},
        route_response_json={"query": query, **routing}, agent_response_json={},
        latency_json={"route_latency_ms": route_latency, "total_latency_ms": round((perf_counter() - started) * 1000)},
        handoff_suggested=True, handoff_reason="agent_failed", status="failed", error_message=str(exc),
    )
