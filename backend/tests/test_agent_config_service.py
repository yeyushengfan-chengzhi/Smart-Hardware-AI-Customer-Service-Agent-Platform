from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.agent_config import AgentConfig
from app.models.agent_prompt_version import AgentPromptVersion
from app.routers.agents import get_agent, list_agents, update_agent_prompt, update_agent_status
from app.schemas import AgentPromptUpdateRequest, AgentStatusRequest
from app.services.agent_config_service import seed_agent_configs


def _database():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[AgentConfig.__table__, AgentPromptVersion.__table__])
    return sessionmaker(bind=engine)()


def test_seed_creates_four_agents_and_initial_prompt_history_idempotently():
    db = _database()
    seed_agent_configs(db)
    seed_agent_configs(db)

    agents = list(db.scalars(select(AgentConfig).order_by(AgentConfig.id)))
    versions = list(db.scalars(select(AgentPromptVersion)))
    assert [agent.agent_name for agent in agents] == [
        "SupervisorAgent", "KnowledgeAgent", "DiagnosisAgent", "ToolAgent",
    ]
    assert len(versions) == 4
    assert all(item.version == "v1" for item in versions)
    assert next(agent for agent in agents if agent.agent_name == "ToolAgent").enabled_tools == [
        "compatibility_check_tool",
        "pc_build_compatibility_tool",
    ]


def test_management_operations_keep_prompt_history():
    db = _database()
    seed_agent_configs(db)

    assert len(list_agents(db)) == 4
    knowledge = get_agent("KnowledgeAgent", db)
    assert knowledge.prompt
    assert knowledge.knowledge_binding == ["B850_manual"]

    updated_status = update_agent_status("ToolAgent", AgentStatusRequest(status="inactive"), db)
    assert updated_status.status == "inactive"

    updated = update_agent_prompt(
        "KnowledgeAgent", AgentPromptUpdateRequest(prompt="Updated knowledge prompt", version="v2"), db
    )
    assert updated.version == "v2"
    assert [item.version for item in updated.prompt_versions] == ["v2", "v1"]
