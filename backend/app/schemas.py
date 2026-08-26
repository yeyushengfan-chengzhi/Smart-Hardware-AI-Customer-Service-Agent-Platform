"""Pydantic request and response schemas."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=128)


class RegisterResponse(BaseModel):
    message: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DemoAccountResponse(BaseModel):
    username: str
    role: Literal["user", "agent", "admin"]


class DemoAccountsResponse(BaseModel):
    accounts: list[DemoAccountResponse]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ChatResponse(BaseModel):
    answer: str


class HistoryMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    created_time: datetime

    model_config = {"from_attributes": True}


class ChatSessionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class ChatSessionResponse(BaseModel):
    session_id: int
    title: str
    last_message: str = ""
    created_time: datetime
    updated_time: datetime


class ChatMessageCreateRequest(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=20000)
    metadata: dict[str, object] = Field(default_factory=dict)


class ChatSessionMessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    metadata: dict[str, object]
    created_time: datetime


TicketStatus = Literal["open", "processing", "resolved", "closed"]
TicketPriority = Literal["low", "medium", "high", "urgent"]
TicketSource = Literal["ai_handoff", "user_request"]


class TicketCreateRequest(BaseModel):
    session_id: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=5000)
    priority: TicketPriority = "medium"
    source: TicketSource = "user_request"
    trace_id: str | None = Field(default=None, max_length=36)


class TicketCreateResponse(BaseModel):
    ticket_id: str
    status: TicketStatus


class TicketListItemResponse(BaseModel):
    ticket_id: str
    user_id: int
    title: str
    source: TicketSource
    status: TicketStatus
    priority: TicketPriority
    created_time: datetime
    updated_time: datetime


class TicketMessageResponse(BaseModel):
    id: int
    sender_type: Literal["customer", "ai", "human_agent"]
    content: str
    created_time: datetime


class TicketDetailResponse(BaseModel):
    ticket_id: str
    user_id: int
    session_id: int
    title: str
    description: str
    source: TicketSource
    status: TicketStatus
    priority: TicketPriority
    trace_id: str | None
    agent_name: str | None
    handoff_reason: str
    agent_result: dict[str, object]
    messages: list[TicketMessageResponse]
    created_time: datetime
    updated_time: datetime


class TicketStatusUpdateRequest(BaseModel):
    status: TicketStatus


class TicketMessageCreateRequest(BaseModel):
    sender_type: Literal["human_agent"] = "human_agent"
    content: str = Field(min_length=1, max_length=20000)


class KnowledgeDocumentResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    file_type: str
    file_hash: str | None = None
    original_filename: str = ""
    vendor: str = ""
    product_name: str = ""
    product_category: str = ""
    document_type: str = ""
    source_url: str = ""
    file_url: str = ""
    support_url: str = ""
    verified: bool = False
    needs_review: bool = False
    source_type: str = ""
    version: str = "1.0"
    status: str = "active"
    chunk_count: int = 0
    embedding_status: str = "pending"
    created_time: datetime
    updated_time: datetime | None = None

    model_config = {"from_attributes": True}


class KnowledgeUploadResponse(BaseModel):
    id: int
    document_id: int
    filename: str
    hash: str
    status: str
    message: str


class ManualSeedImportDetail(BaseModel):
    index: int
    status: Literal["imported", "skipped", "failed"]
    original_filename: str = ""
    product_name: str = ""
    document_id: int | None = None
    reason: str


class ManualSeedImportResponse(BaseModel):
    total: int
    imported: int
    skipped: int
    failed: int
    needs_review: int = 0
    details: list[ManualSeedImportDetail]


class ManualSeedStatusResponse(BaseModel):
    manifest_total: int
    manifest_downloaded: int
    manifest_needs_review: int
    manifest_failed: int
    imported_documents: int
    completed_documents: int
    processing_documents: int
    failed_documents: int
    total_chunks: int
    categories: dict[str, int]


class ParseDocumentResponse(BaseModel):
    message: str
    chunks: int


class KnowledgeChunkResponse(BaseModel):
    id: int
    document_id: int
    content: str
    chunk_index: int
    page_number: int | None
    section_title: str
    created_time: datetime

    model_config = {"from_attributes": True}


class EmbeddingTestRequest(BaseModel):
    texts: list[Annotated[str, Field(min_length=1, max_length=5000)]] = Field(
        min_length=1,
        max_length=100,
    )


class EmbeddingTestResponse(BaseModel):
    count: int
    dimension: int


class VectorizeDocumentResponse(BaseModel):
    message: str
    vectors: int


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=3, ge=1, le=20)


class KnowledgeSearchItem(BaseModel):
    chunk_id: int
    document_id: int
    content: str
    distance: float


class KnowledgeSearchResponse(BaseModel):
    results: list[KnowledgeSearchItem]


class KnowledgeAdminChunkResponse(BaseModel):
    chunk_id: int
    content: str
    page_number: int | None
    section_title: str


class KnowledgeSearchTestItem(BaseModel):
    content: str
    filename: str
    page_number: int | None
    section_title: str
    score: float
    source_type: str = ""
    source_label: str = ""


class KnowledgeSearchTestResponse(BaseModel):
    results: list[KnowledgeSearchTestItem]


class KnowledgeVectorStatusResponse(BaseModel):
    document_id: int
    filename: str
    status: str
    embedding_status: str
    db_chunk_count: int
    vector_count: int
    metadata_samples: list[dict[str, object]]


class KnowledgeDocumentStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=3, ge=1, le=10)

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "我的主板开机没有显示怎么办",
                    "top_k": 3,
                }
            ]
        }
    }


class RAGSearchItem(BaseModel):
    content: str
    score: float = Field(ge=0.0, le=1.0)
    semantic_score: float = Field(ge=0.0, le=1.0)
    keyword_score: float = Field(ge=0.0, le=1.0)
    filename: str
    page_number: int | None
    section_title: str
    chunk_id: int
    document_id: int
    source_type: str = ""
    source_label: str = ""


class RAGSearchResponse(BaseModel):
    query: str
    count: int
    results: list[RAGSearchItem]


class RAGChatRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)

    model_config = {
        "json_schema_extra": {
            "examples": [{"query": "我的主板开机没有显示怎么办"}]
        }
    }


class RAGChatSource(BaseModel):
    filename: str
    page_number: int | None
    section_title: str
    source_type: str = ""
    source_label: str = ""


class RAGChatResponse(BaseModel):
    query: str
    answer: str
    sources: list[RAGChatSource]


class AgentRouteRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)

    model_config = {
        "json_schema_extra": {
            "examples": [{"query": "我的主板开机没有显示怎么办"}]
        }
    }


class AgentRouteResponse(BaseModel):
    query: str
    intent: str
    device_type: str
    fault_type: str
    route: str
    trace_id: str | None = None


class DiagnosisRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)


class DiagnosisSource(BaseModel):
    filename: str
    page_number: int | None
    section_title: str
    source_type: str = ""
    source_label: str = ""


class DiagnosisStep(BaseModel):
    action: str
    reason: str
    sources: list[DiagnosisSource]


class DiagnosisResponse(BaseModel):
    query: str
    device: str
    fault_type: str
    steps: list[DiagnosisStep]
    trace_id: str | None = None


class AgentKnowledgeRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=3, ge=1, le=10)


class AgentKnowledgeSource(BaseModel):
    filename: str
    page_number: int | None
    section_title: str
    source_type: str = ""
    source_label: str = ""


class AgentKnowledgeResponse(BaseModel):
    query: str
    answer: str
    sources: list[AgentKnowledgeSource]
    trace_id: str | None = None


class AgentToolRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)


class AgentToolResponse(BaseModel):
    query: str
    tool_name: str | None
    tool_input: dict[str, str]
    tool_result: dict[str, object]
    answer: str
    sources: list[AgentKnowledgeSource] = Field(default_factory=list)
    trace_id: str | None = None


class AgentStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|inactive)$")


class AgentPromptUpdateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    version: str = Field(pattern=r"^v[1-9][0-9]*$")


class AgentListItem(BaseModel):
    agent_name: str
    type: str = Field(validation_alias="agent_type", serialization_alias="type")
    status: str
    version: str
    updated_time: datetime
    model_config = {"from_attributes": True, "populate_by_name": True}


class AgentPromptVersionResponse(BaseModel):
    version: str
    prompt: str
    created_time: datetime
    model_config = {"from_attributes": True}


class AgentDetailResponse(BaseModel):
    agent_name: str
    type: str
    description: str
    status: str
    prompt: str
    version: str
    tools: list[str]
    knowledge_binding: list[str]
    updated_time: datetime
    prompt_versions: list[AgentPromptVersionResponse]


class AgentTraceListItem(BaseModel):
    trace_id: str
    query: str
    route: str
    agent_name: str
    status: str
    handoff_suggested: bool
    total_latency_ms: int | None = None
    created_time: datetime


class AgentTraceDetail(BaseModel):
    trace_id: str
    query: str
    route: str
    intent: str
    device_type: str
    fault_type: str
    agent_name: str
    final_answer: str
    sources: list[dict[str, object]]
    tool_name: str
    tool_input: dict[str, object]
    tool_result: dict[str, object]
    route_response: dict[str, object]
    agent_response: dict[str, object]
    latency: dict[str, object]
    handoff_suggested: bool
    handoff_reason: str
    status: str
    error_message: str
    created_time: datetime


class EvaluationCaseCreate(BaseModel):
    question: str = Field(min_length=1, max_length=5000)
    expected_route: str = Field(min_length=1, max_length=32)
    expected_agent: str = Field(min_length=1, max_length=64)
    expected_keywords: list[str] = Field(default_factory=list)
    expected_tool: str = Field(default="", max_length=128)
    expected_answer: str = ""
    category: str = Field(pattern="^(knowledge|diagnosis|tool|general|handoff)$")


class EvaluationCaseResponse(EvaluationCaseCreate):
    id: int
    created_time: datetime

    model_config = {"from_attributes": True}


class EvaluationRunRequest(BaseModel):
    run_name: str = Field(min_length=1, max_length=255)


class EvaluationRunResponse(BaseModel):
    run_id: int
    total_cases: int
    passed_cases: int
    failed_cases: int
    pass_rate: float


class EvaluationResultResponse(BaseModel):
    id: int
    run_id: int
    case_id: int
    trace_id: str
    question: str
    actual_route: str
    expected_route: str
    route_match: bool
    actual_agent: str
    expected_agent: str
    agent_match: bool
    expected_tool: str
    actual_tool: str
    keyword_score: float
    tool_match: bool
    score: float
    status: str
    error_message: str
    created_time: datetime
