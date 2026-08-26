"""Read-only Agent Trace query endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AgentTraceDetail, AgentTraceListItem
from app.security import require_admin
from app.services.trace_service import get_trace, query_traces

router = APIRouter(prefix="/traces", tags=["traces"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[AgentTraceListItem])
def list_agent_traces(
    route: str | None = None,
    agent_name: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[AgentTraceListItem]:
    return [
        AgentTraceListItem(
            trace_id=item.trace_id,
            query=item.query,
            route=item.route,
            agent_name=item.agent_name,
            status=item.status,
            handoff_suggested=item.handoff_suggested,
            total_latency_ms=item.latency_json.get("total_latency_ms"),
            created_time=item.created_time,
        )
        for item in query_traces(db, route, agent_name, status_filter, limit)
    ]


@router.get("/{trace_id}", response_model=AgentTraceDetail)
def get_agent_trace(trace_id: str, db: Session = Depends(get_db)) -> AgentTraceDetail:
    item = get_trace(db, trace_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="agent trace not found")
    return AgentTraceDetail(
        trace_id=item.trace_id, query=item.query, route=item.route, intent=item.intent,
        device_type=item.device_type, fault_type=item.fault_type, agent_name=item.agent_name,
        final_answer=item.final_answer, sources=item.sources_json or [], tool_name=item.tool_name,
        tool_input=item.tool_input_json or {}, tool_result=item.tool_result_json or {},
        route_response=item.route_response_json or {}, agent_response=item.agent_response_json or {},
        latency=item.latency_json or {}, handoff_suggested=item.handoff_suggested,
        handoff_reason=item.handoff_reason, status=item.status, error_message=item.error_message,
        created_time=item.created_time,
    )
