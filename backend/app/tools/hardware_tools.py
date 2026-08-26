"""Data-driven local hardware specification and compatibility tools."""

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


HARDWARE_SPECS_FILE = Path(__file__).resolve().parent.parent / "data" / "hardware_specs.json"
SOURCE_FIELDS = ("source_file", "source_page", "source_section")


@lru_cache(maxsize=1)
def _load_hardware_specs() -> dict[str, dict]:
    """Load the bundled, version-controlled hardware catalogue once."""
    with HARDWARE_SPECS_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def hardware_spec_tool(product: str) -> dict:
    """Return the locally registered specification for *product*."""
    normalized_product = product.strip().upper()
    specification = _load_hardware_specs().get(normalized_product)
    if specification is None:
        return {
            "status": "unknown",
            "reason": f"本地规格数据暂未收录 {product.strip() or '该产品'}。",
        }
    result = deepcopy(specification)
    # Preserve the existing ToolAgent response contract while exposing the
    # canonical series field used by the data file and compatibility engine.
    result["cpu_support"] = [
        f"AMD {series}" for series in result.get("cpu_support_series", [])
    ]
    return result


def compatibility_check_tool(cpu: str, motherboard: str) -> dict:
    """Apply conservative local rules to a CPU and motherboard pair."""
    normalized_cpu = cpu.strip().casefold()
    normalized_motherboard = motherboard.strip().upper()
    specification = _load_hardware_specs().get(normalized_motherboard)
    if specification is None:
        return {
            "compatible": "unknown",
            "reason": f"本地规格数据暂未收录 {motherboard.strip() or '该主板'}。",
        }

    source = {field: specification.get(field) for field in SOURCE_FIELDS}
    matched_example = next(
        (
            example
            for example in specification.get("cpu_support_examples", [])
            if example.casefold() in normalized_cpu
        ),
        None,
    )
    matched_series = next(
        (
            series
            for series in specification.get("cpu_support_series", [])
            if series.casefold() in normalized_cpu
        ),
        None,
    )

    if matched_example or matched_series:
        match_reason = (
            f"{cpu.strip()}在{normalized_motherboard}的CPU支持示例中"
            if matched_example
            else f"{normalized_motherboard}支持{matched_series}系列处理器"
        )
        return {
            "compatible": True,
            "reason": f"{match_reason}，主板插槽为{specification['socket']}。",
            **source,
        }
    return {
        "compatible": "unknown",
        "reason": (
            f"当前本地硬件规格数据无法确认该CPU与{normalized_motherboard}主板兼容，"
            "建议转人工或查询官方CPU支持列表和BIOS版本。"
        ),
        **source,
    }
