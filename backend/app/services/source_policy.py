"""Knowledge-source labels and deterministic community-experience safeguards."""

from collections.abc import Mapping, Sequence


OFFICIAL_MANUAL_SOURCE_TYPE = "official_manual_seed"
COMMUNITY_EXPERIENCE_SOURCE_TYPE = "community_experience"
COMMUNITY_USAGE_POLICY = "社区经验仅作为装机风险提示，不代表官方规格结论。"
COMMUNITY_ONLY_REMINDER = "请最终以官方说明书或实际产品参数为准。"

SOURCE_LABELS = {
    OFFICIAL_MANUAL_SOURCE_TYPE: "官方说明书依据",
    COMMUNITY_EXPERIENCE_SOURCE_TYPE: "社区经验提示",
}


def source_label(source_type: object) -> str:
    """Return a user-facing label while preserving unknown source types."""
    value = str(source_type or "")
    return SOURCE_LABELS.get(value, value or "知识库来源")


def source_types(contexts: Sequence[Mapping[str, object]]) -> set[str]:
    return {
        str(context.get("source_type") or "")
        for context in contexts
        if context.get("source_type")
    }


def apply_source_policy(
    answer: str, contexts: Sequence[Mapping[str, object]]
) -> str:
    """Append mandatory source-priority language when community data was used."""
    types = source_types(contexts)
    if COMMUNITY_EXPERIENCE_SOURCE_TYPE not in types:
        return answer

    parts = [answer.rstrip()]
    if OFFICIAL_MANUAL_SOURCE_TYPE in types:
        priority_note = "官方说明书结论优先，社区经验仅作为补充提示。"
        if priority_note not in answer:
            parts.append(priority_note)
    elif COMMUNITY_ONLY_REMINDER not in answer:
        parts.append(COMMUNITY_ONLY_REMINDER)
    if COMMUNITY_USAGE_POLICY not in answer:
        parts.append(COMMUNITY_USAGE_POLICY)
    return "\n\n".join(part for part in parts if part)
