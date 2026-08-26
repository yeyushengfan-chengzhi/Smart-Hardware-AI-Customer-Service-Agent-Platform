from app.services.document_parser_service import (
    CHUNK_OVERLAP,
    MAX_CHUNK_SIZE,
    clean_text,
    split_page,
)


def test_clean_text_removes_noise_but_keeps_hardware_terms():
    raw = "51\\n11 22 33 44\n.● .BIOS. 检查 GPU、DRAM 和 CMOS。\nhttps://x.test\nhttps://x.test"
    cleaned = clean_text(raw)
    assert "11 22 33 44" not in cleaned
    assert "51" not in cleaned
    assert cleaned.count("https://x.test") <= 1
    assert all(term in cleaned for term in ("BIOS", "GPU", "DRAM", "CMOS"))


def test_heading_page_metadata_max_length_and_overlap():
    text = "板载 LED 灯\n简易侦错 LED 灯\n" + ("白色 GPU 无法检测或故障。黄色 DRAM 无法检测或故障。" * 80)
    chunks = split_page(text, 51)
    assert len(chunks) > 1
    assert all(len(chunk.content) <= MAX_CHUNK_SIZE for chunk in chunks)
    assert all(chunk.page_number == 51 for chunk in chunks)
    assert all("简易侦错 LED 灯" in chunk.section_title for chunk in chunks)
    assert chunks[0].content[-CHUNK_OVERLAP // 2 :] in chunks[1].content


def test_empty_and_numeric_only_pages_are_discarded():
    assert split_page("1\n22 33 44\nhttps://only.example", 1) == []


def test_section_title_is_kept_with_body():
    chunks = split_page("板载 LED 灯\n简易侦错 LED 灯\n白色 GPU 无法检测或故障。", 51)
    assert chunks[0].content.startswith("板载 LED 灯")
    assert chunks[0].section_title == "板载 LED 灯 / 简易侦错 LED 灯"


def test_literal_newlines_and_repeated_whitespace_are_normalized():
    assert clean_text("CPU\\n\\n   GPU") == "CPU\n\nGPU"


def test_meaningful_numbered_procedure_is_preserved():
    cleaned = clean_text("1. 关闭计算机电源。\n2. 清除 CMOS。")
    assert "1. 关闭" in cleaned
    assert "2. 清除 CMOS" in cleaned
