"""Agent configuration defaults and version-history helpers.

This module is intentionally not used by the runtime routing/agent code yet.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_config import AgentConfig
from app.models.agent_prompt_version import AgentPromptVersion

DEFAULT_AGENTS = [
    {"agent_name": "SupervisorAgent", "agent_type": "supervisor", "description": "Routes customer requests to the appropriate specialist agent.", "system_prompt": "You are the SupervisorAgent. Classify the request and route it to the appropriate specialist.", "enabled_tools": [], "knowledge_binding": []},
    {"agent_name": "KnowledgeAgent", "agent_type": "knowledge", "description": "Answers product and manual questions with RAG knowledge.", "system_prompt": "You are the KnowledgeAgent. Answer accurately from the retrieved product knowledge.", "enabled_tools": [], "knowledge_binding": ["B850_manual"]},
    {"agent_name": "DiagnosisAgent", "agent_type": "diagnosis", "description": "Provides structured hardware troubleshooting steps.", "system_prompt": "You are the DiagnosisAgent. Provide safe, ordered hardware diagnostic steps.", "enabled_tools": [], "knowledge_binding": ["GPU_FAQ"]},
    {"agent_name": "ToolAgent", "agent_type": "tool", "description": "Performs structured hardware compatibility checks.", "system_prompt": "You are the ToolAgent. Use the available compatibility tools when needed.", "enabled_tools": ["compatibility_check_tool", "pc_build_compatibility_tool"], "knowledge_binding": []},
]


def seed_agent_configs(db: Session) -> None:
    for defaults in DEFAULT_AGENTS:
        existing = db.scalar(select(AgentConfig).where(AgentConfig.agent_name == defaults["agent_name"]))
        if existing is None:
            config = AgentConfig(**defaults, status="active", version="v1")
            db.add(config)
            db.flush()
            db.add(AgentPromptVersion(agent_name=config.agent_name, version="v1", prompt=config.system_prompt))
        elif existing.agent_name == "ToolAgent":
            existing.enabled_tools = defaults["enabled_tools"]
    db.commit()
