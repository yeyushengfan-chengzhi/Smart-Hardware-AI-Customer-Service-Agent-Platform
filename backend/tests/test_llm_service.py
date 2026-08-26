import json

import pytest

from app.services.llm_service import LLMService, LLMServiceError


class FakeSettings:
    llm_provider = "deepseek"
    llm_api_key = "test-key"
    llm_model = "deepseek-chat"


def test_prompt_contains_query_context_and_grounding_rules():
    service = LLMService(FakeSettings())
    messages = service._build_messages(
        "显卡无法检测怎么办",
        [{
            "filename": "manual.pdf",
            "page_number": 51,
            "section_title": "简易侦错 LED 灯",
            "content": "白色 LED 表示 GPU 无法检测或故障。",
        }],
    )

    prompt = json.dumps(messages, ensure_ascii=False)
    assert "显卡无法检测怎么办" in prompt
    assert "白色 LED 表示 GPU 无法检测或故障" in prompt
    assert "不得编造硬件参数" in prompt
    assert "不得自行补充任何具体数字" in prompt
    assert "请参考产品说明书或联系人工客服确认" in prompt
    assert "回答最后附上联系人工客服的建议" in prompt
    assert "manual.pdf" in prompt


def test_missing_api_key_fails_before_network_call():
    settings = FakeSettings()
    settings.llm_api_key = ""
    with pytest.raises(LLMServiceError, match="LLM_API_KEY"):
        LLMService(settings).generate_answer("如何清除CMOS", [])
