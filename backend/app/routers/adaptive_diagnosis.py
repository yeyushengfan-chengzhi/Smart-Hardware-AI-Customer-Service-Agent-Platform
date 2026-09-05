"""API for multi-turn, adaptive hardware troubleshooting."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.adaptive_diagnosis_service import adaptive_diagnosis_service


router = APIRouter(prefix="/agent/diagnosis", tags=["agent"])


class DiagnosisObservation(BaseModel):
    check_id: str = Field(min_length=1, max_length=64)
    outcome: Literal[
        "normal", "abnormal", "unknown", "pass", "fail", "正常", "异常", "不确定"
    ]


class AdaptiveDiagnosisRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    fault_type: str = Field(default="unknown", max_length=64)
    observations: list[DiagnosisObservation] = Field(default_factory=list, max_length=20)


class AdaptiveDiagnosisResponse(BaseModel):
    status: Literal["in_progress", "complete", "safety_stop"]
    profile: str
    next_check: dict[str, object] | None
    hypotheses: list[dict[str, object]]
    confidence: float = Field(ge=0, le=1)
    should_handoff: bool
    stop_reason: str
    explanation: str


@router.post("/next-check", response_model=AdaptiveDiagnosisResponse)
def select_next_diagnostic_check(
    payload: AdaptiveDiagnosisRequest,
) -> AdaptiveDiagnosisResponse:
    """Use prior check outcomes to choose the next most useful and safe check."""
    result = adaptive_diagnosis_service.next_check(
        query=payload.query,
        fault_type=payload.fault_type,
        observations=[item.model_dump() for item in payload.observations],
    )
    return AdaptiveDiagnosisResponse(**result)
