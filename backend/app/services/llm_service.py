"""LLM provider integration and grounded customer-service prompt construction."""

import json
from typing import Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings, get_settings
from app.services.source_policy import source_label


SYSTEM_PROMPT = """你是一名专业、耐心的智能硬件售后客服。
请严格遵守以下规则：
1. 只能依据提供的知识库上下文回答，不得使用上下文之外的信息。
2. 如果知识库没有明确给出时间、数值、型号或参数，不得自行补充任何具体数字。
3. 可以给出知识库支持的通用排查步骤；涉及具体操作时长、规格或参数时，必须严格以知识库原文为准。
4. 对知识库未明确说明的细节，必须使用“请参考产品说明书或联系人工客服确认”。
5. 不得编造硬件参数、故障原因或操作方法。
6. 优先给出可执行的排查步骤，并使用从 1 开始的编号列表。
7. 使用简洁、礼貌的中文回答，并在回答最后附上联系人工客服的建议。
8. 标记为“官方说明书依据”的内容优先级最高；社区经验不能覆盖官方结论。
9. 标记为“社区经验提示”的内容只能用于补充装机风险。若只有社区经验，
   必须使用“可能”“建议核对”等保守语气，不得输出确定性规格或兼容结论，
   并提醒用户最终以官方说明书或实际产品参数为准。"""


class LLMServiceError(RuntimeError):
    """Raised when LLM configuration or provider communication fails."""


class LLMService:
    """Build grounded prompts and call the configured LLM provider."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _build_messages(
        self, query: str, contexts: Sequence[Mapping[str, object]]
    ) -> list[dict[str, str]]:
        if contexts:
            context_text = "\n\n".join(
                "[知识 {index}] 来源：{source_label}；source_type={source_type}；"
                "文件：{filename}；页码：{page}; 章节：{section}\n{content}".format(
                    index=index,
                    source_label=source_label(context.get("source_type")),
                    source_type=context.get("source_type") or "unknown",
                    filename=context.get("filename") or "未知",
                    page=context.get("page_number") if context.get("page_number") is not None else "未知",
                    section=context.get("section_title") or "未标注",
                    content=context.get("content") or "",
                )
                for index, context in enumerate(contexts, start=1)
            )
        else:
            context_text = "（本次检索没有找到相关知识）"

        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"知识库上下文：\n{context_text}\n\n用户问题：{query}\n\n请生成客服回答。",
            },
        ]

    def generate_answer(
        self, query: str, contexts: Sequence[Mapping[str, object]]
    ) -> str:
        """Return a grounded answer for the user query."""
        if self.settings.llm_provider.casefold() != "deepseek":
            raise LLMServiceError(f"unsupported LLM provider: {self.settings.llm_provider}")
        if not self.settings.llm_api_key:
            raise LLMServiceError("LLM_API_KEY is not configured")

        payload = json.dumps(
            {
                "model": self.settings.llm_model,
                "messages": self._build_messages(query, contexts),
                "temperature": 0.2,
                "stream": False,
            },
            ensure_ascii=False,
        ).encode("utf-8")
        request = Request(
            "https://api.deepseek.com/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                result = json.loads(response.read().decode("utf-8"))
            answer = result["choices"][0]["message"]["content"].strip()
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
            raise LLMServiceError("LLM request failed") from exc
        if not answer:
            raise LLMServiceError("LLM returned an empty answer")
        return answer


llm_service = LLMService()
