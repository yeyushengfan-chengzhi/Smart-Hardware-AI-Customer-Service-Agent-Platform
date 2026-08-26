from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.tool_agent import ToolAgent
from app.services.source_policy import (
    COMMUNITY_USAGE_POLICY,
    apply_source_policy,
)


COMMUNITY_CONTEXT = {
    "chunk_id": 7,
    "document_id": 3,
    "filename": "community_experience_seed.md",
    "page_number": 1,
    "section_title": "厚显卡与底部风扇空间风险",
    "content": "厚显卡可能遮挡底部风扇，需要核对实际空间风险。",
    "source_type": "community_experience",
    "source_label": "社区经验提示",
}


def test_community_only_answer_gets_conservative_reminder_and_disclaimer():
    answer = apply_source_policy("这种情况可能存在空间干涉。", [COMMUNITY_CONTEXT])

    assert "最终以官方说明书或实际产品参数为准" in answer
    assert answer.endswith(COMMUNITY_USAGE_POLICY)


def test_knowledge_agent_preserves_community_source_metadata():
    class Retriever:
        def search(self, query, top_k):
            return [COMMUNITY_CONTEXT]

    class Generator:
        def generate_answer(self, query, contexts):
            return "建议核对实际安装空间。"

    result = KnowledgeAgent(Retriever(), Generator()).answer("厚显卡会挡风扇吗")

    assert result["sources"][0]["source_type"] == "community_experience"
    assert result["sources"][0]["source_label"] == "社区经验提示"
    assert result["answer"].endswith(COMMUNITY_USAGE_POLICY)


def test_tool_result_remains_primary_and_trace_sources_include_community():
    class Retriever:
        def search(self, query, top_k):
            return [COMMUNITY_CONTEXT]

    result = ToolAgent(retriever=Retriever()).run("厚显卡会不会挡底部风扇？")

    assert result["tool_name"] == "pc_build_compatibility_tool"
    assert result["tool_result"]["primary_check"] == "gpu_bottom_fan_risk"
    assert result["sources"][0]["source_type"] == "community_experience"
    assert "社区经验补充" in result["answer"]
    assert result["answer"].endswith(COMMUNITY_USAGE_POLICY)
