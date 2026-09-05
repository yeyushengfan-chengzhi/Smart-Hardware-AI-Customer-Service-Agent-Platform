"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import init_database
from app.routers.agent import router as agent_router
from app.routers.adaptive_diagnosis import router as adaptive_diagnosis_router
from app.routers.agents import router as agents_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.dev import router as dev_router
from app.routers.evaluation import router as evaluation_router
from app.routers.health import router as health_router
from app.routers.knowledge import router as knowledge_router
from app.routers.rag import router as rag_router
from app.routers.trace import router as trace_router
from app.routers.tickets import router as tickets_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables when the application starts."""
    init_database()
    yield


app = FastAPI(
    title="Smart Hardware AI Customer Service Agent Platform",
    lifespan=lifespan,
)
app.include_router(health_router)
app.include_router(auth_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(dev_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(adaptive_diagnosis_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(trace_router, prefix="/api")
app.include_router(evaluation_router, prefix="/api")
app.include_router(tickets_router, prefix="/api")
