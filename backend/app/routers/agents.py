"""Admin-only configuration endpoints for the existing multi-agent topology."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.agent_config import AgentConfig
from app.models.agent_prompt_version import AgentPromptVersion
from app.schemas import AgentDetailResponse, AgentListItem, AgentPromptUpdateRequest, AgentPromptVersionResponse, AgentStatusRequest
from app.security import require_admin

router = APIRouter(prefix="/agents", tags=["agents"], dependencies=[Depends(require_admin)])


def get_agent_or_404(agent_name: str, db: Session) -> AgentConfig:
    agent = db.scalar(select(AgentConfig).where(AgentConfig.agent_name == agent_name))
    if agent is None:
        raise HTTPException(status_code=404, detail="agent does not exist")
    return agent


@router.get("", response_model=list[AgentListItem])
def list_agents(db: Session = Depends(get_db)):
    return list(db.scalars(select(AgentConfig).order_by(AgentConfig.id)).all())


@router.get("/{agent_name}", response_model=AgentDetailResponse)
def get_agent(agent_name: str, db: Session = Depends(get_db)):
    agent = get_agent_or_404(agent_name, db)
    versions = list(db.scalars(select(AgentPromptVersion).where(AgentPromptVersion.agent_name == agent_name).order_by(AgentPromptVersion.created_time.desc(), AgentPromptVersion.id.desc())).all())
    return AgentDetailResponse(agent_name=agent.agent_name, type=agent.agent_type, description=agent.description, status=agent.status, prompt=agent.system_prompt, version=agent.version, tools=agent.enabled_tools or [], knowledge_binding=agent.knowledge_binding or [], updated_time=agent.updated_time, prompt_versions=[AgentPromptVersionResponse.model_validate(item) for item in versions])


@router.patch("/{agent_name}/status", response_model=AgentListItem)
def update_agent_status(agent_name: str, payload: AgentStatusRequest, db: Session = Depends(get_db)):
    agent = get_agent_or_404(agent_name, db)
    agent.status = payload.status
    db.commit(); db.refresh(agent)
    return agent


@router.patch("/{agent_name}/prompt", response_model=AgentDetailResponse)
def update_agent_prompt(agent_name: str, payload: AgentPromptUpdateRequest, db: Session = Depends(get_db)):
    agent = get_agent_or_404(agent_name, db)
    if db.scalar(select(AgentPromptVersion).where(AgentPromptVersion.agent_name == agent_name, AgentPromptVersion.version == payload.version)):
        raise HTTPException(status_code=409, detail="prompt version already exists")
    agent.system_prompt = payload.prompt
    agent.version = payload.version
    db.add(AgentPromptVersion(agent_name=agent_name, version=payload.version, prompt=payload.prompt))
    try:
        db.commit()
    except IntegrityError:
        db.rollback(); raise HTTPException(status_code=409, detail="prompt version already exists")
    return get_agent(agent_name, db)
