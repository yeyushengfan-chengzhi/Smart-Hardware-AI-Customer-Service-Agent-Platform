from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.evaluation_case import EvaluationCase
from app.models.evaluation_result import EvaluationResult
from app.models.evaluation_run import EvaluationRun
from app.services import evaluation_service


def _database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            EvaluationCase.__table__,
            EvaluationRun.__table__,
            EvaluationResult.__table__,
        ],
    )
    return sessionmaker(bind=engine)()


def test_seed_creates_enterprise_suite_idempotently():
    db = _database()
    assert evaluation_service.seed_default_cases(db) == 77
    assert evaluation_service.seed_default_cases(db) == 0
    cases = list(db.scalars(select(EvaluationCase)).all())
    assert len(cases) == 77
    cooling_cases = [
        case for case in cases
        if case.expected_tool == "pc_build_compatibility_tool"
        and "expected_result_type" in case.expected_answer
    ]
    assert len(cooling_cases) == 10
    community_cases = [
        case for case in cases
        if "expected_source_type" in case.expected_answer
    ]
    assert len(community_cases) == 5
    assert {case.category for case in cases} == {"knowledge", "diagnosis", "tool", "general", "handoff"}


def test_duplicate_questions_can_have_different_targets():
    db = _database()
    db.add_all([
        EvaluationCase(question="同一个问题", expected_route="knowledge", expected_agent="KnowledgeAgent", expected_keywords=[], expected_tool="", expected_answer="", category="knowledge"),
        EvaluationCase(question="同一个问题", expected_route="tool", expected_agent="ToolAgent", expected_keywords=[], expected_tool="hardware_spec_tool", expected_answer="", category="tool"),
    ])
    db.commit()
    assert len(db.scalars(select(EvaluationCase)).all()) == 2


def test_existing_phase73_case_is_upgraded_with_community_source_expectation():
    db = _database()
    db.add(EvaluationCase(
        question="双塔风冷会不会挡高马甲内存？",
        expected_route="tool",
        expected_agent="ToolAgent",
        expected_keywords=["高马甲内存"],
        expected_tool="pc_build_compatibility_tool",
        expected_answer="",
        category="tool",
    ))
    db.commit()

    evaluation_service.seed_default_cases(db)

    upgraded = db.scalar(select(EvaluationCase).where(
        EvaluationCase.question == "双塔风冷会不会挡高马甲内存？"
    ))
    assert "expected_source_type" in upgraded.expected_answer
    assert "双塔风冷" in upgraded.expected_keywords


def test_run_persists_result_and_trace_id(monkeypatch):
    db = _database()
    db.add(EvaluationCase(
        question="9700X可以搭配B850主板吗", expected_route="tool",
        expected_agent="ToolAgent", expected_keywords=["兼容"],
        expected_tool="compatibility_check_tool", expected_answer="", category="tool",
    ))
    db.commit()
    trace = SimpleNamespace(
        trace_id="trace-1", route="tool", agent_name="ToolAgent",
        tool_name="compatibility_check_tool", final_answer="该组合兼容",
        agent_response_json={},
    )
    monkeypatch.setattr(evaluation_service, "_execute_agent", lambda _: "trace-1")
    monkeypatch.setattr(evaluation_service, "_load_trace", lambda _: trace)

    run = evaluation_service.execute_evaluation(db, "regression")
    result = db.scalar(select(EvaluationResult))

    assert run.total_cases == 1
    assert run.passed_cases == 1
    assert run.pass_rate == 1.0
    assert result.trace_id == "trace-1"
    assert result.final_score == 100.0
    assert result.expected_tool == "compatibility_check_tool"
    assert result.actual_tool == "compatibility_check_tool"
    assert result.status == "passed"


def test_failed_case_records_reason(monkeypatch):
    db = _database()
    db.add(EvaluationCase(
        question="route regression", expected_route="knowledge",
        expected_agent="KnowledgeAgent", expected_keywords=["DDR5"],
        expected_tool="", expected_answer="", category="knowledge",
    ))
    db.commit()
    trace = SimpleNamespace(
        trace_id="trace-2", route="diagnosis", agent_name="DiagnosisAgent",
        tool_name="", final_answer="未找到答案", agent_response_json={},
    )
    monkeypatch.setattr(evaluation_service, "_execute_agent", lambda _: "trace-2")
    monkeypatch.setattr(evaluation_service, "_load_trace", lambda _: trace)

    evaluation_service.execute_evaluation(db, "failed regression")
    result = db.scalar(select(EvaluationResult))

    assert result.status == "failed"
    assert result.trace_id == "trace-2"
    assert "route mismatch" in result.error_message
    assert "agent mismatch" in result.error_message
