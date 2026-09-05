"""Rule-based Evaluation API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evaluation_case import EvaluationCase
from app.models.evaluation_result import EvaluationResult
from app.schemas import (
    EvaluationCaseCreate,
    EvaluationCaseResponse,
    EvaluationResultResponse,
    EvaluationRunRequest,
    EvaluationRunResponse,
)
from app.security import require_admin
from app.services.benchmark_service import evaluate_benchmark
from app.services.evaluation_service import execute_evaluation

router = APIRouter(prefix="/evaluation", tags=["evaluation"], dependencies=[Depends(require_admin)])


@router.get("/benchmark")
def get_benchmark_report() -> dict:
    """Run the small offline benchmark without calling an LLM or database."""
    return evaluate_benchmark()


@router.post("/cases", response_model=EvaluationCaseResponse, status_code=status.HTTP_201_CREATED)
def create_case(payload: EvaluationCaseCreate, db: Session = Depends(get_db)) -> EvaluationCase:
    case = EvaluationCase(**payload.model_dump())
    db.add(case)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="evaluation case already exists") from exc
    db.refresh(case)
    return case


@router.get("/cases", response_model=list[EvaluationCaseResponse])
def list_cases(
    category: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[EvaluationCase]:
    statement = select(EvaluationCase)
    if category:
        statement = statement.where(EvaluationCase.category == category)
    return list(db.scalars(statement.order_by(EvaluationCase.id).limit(limit)).all())


@router.post("/run", response_model=EvaluationRunResponse)
def run_evaluation(payload: EvaluationRunRequest, db: Session = Depends(get_db)) -> EvaluationRunResponse:
    run = execute_evaluation(db, payload.run_name)
    return EvaluationRunResponse(
        run_id=run.id, total_cases=run.total_cases, passed_cases=run.passed_cases,
        failed_cases=run.failed_cases, pass_rate=run.pass_rate,
    )


@router.get("/results", response_model=list[EvaluationResultResponse])
def list_results(
    run_id: int | None = None,
    category: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[EvaluationResultResponse]:
    statement = select(EvaluationResult)
    if category:
        statement = statement.join(EvaluationCase, EvaluationCase.id == EvaluationResult.case_id).where(
            EvaluationCase.category == category
        )
    if run_id is not None:
        statement = statement.where(EvaluationResult.run_id == run_id)
    if status_filter:
        statement = statement.where(EvaluationResult.status == status_filter)
    rows = db.scalars(statement.order_by(EvaluationResult.created_time.desc(), EvaluationResult.id.desc()).limit(limit)).all()
    return [
        EvaluationResultResponse(
            id=row.id, run_id=row.run_id, case_id=row.case_id, trace_id=row.trace_id,
            question=row.question, actual_route=row.actual_route, expected_route=row.expected_route,
            route_match=row.route_match, actual_agent=row.actual_agent,
            expected_agent=row.expected_agent, agent_match=row.agent_match,
            expected_tool=row.expected_tool, actual_tool=row.actual_tool,
            keyword_score=row.keyword_score, tool_match=row.tool_match,
            score=row.final_score, status=row.status, error_message=row.error_message,
            created_time=row.created_time,
        )
        for row in rows
    ]
