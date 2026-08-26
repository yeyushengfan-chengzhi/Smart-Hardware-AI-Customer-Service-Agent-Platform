"""Extensible, data-driven PC build compatibility rules."""

import json
import re
from copy import deepcopy
from functools import lru_cache
from pathlib import Path


PC_PARTS_FILE = Path(__file__).resolve().parent.parent / "data" / "pc_parts.json"
INPUT_TO_COLLECTION = {
    "cpu": "cpus",
    "motherboard": "motherboards",
    "case": "cases",
    "gpu": "gpus",
    "cpu_cooler": "cpu_coolers",
    "aio_cooler": "aio_coolers",
    "memory": "memory",
    "psu": "psus",
}
PART_LABELS = {
    "cpu": "CPU",
    "motherboard": "主板",
    "case": "机箱",
    "gpu": "显卡",
    "cpu_cooler": "CPU 散热器",
    "aio_cooler": "一体式水冷",
    "memory": "内存",
    "psu": "电源",
}


@lru_cache(maxsize=1)
def load_pc_parts() -> dict[str, list[dict]]:
    """Load the version-controlled local parts catalogue."""
    with PC_PARTS_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", value.casefold())


def _terms(part: dict) -> list[str]:
    return [part["name"], *part.get("aliases", [])]


def find_pc_part_name(collection: str, text: str) -> str | None:
    """Return the most specific catalogue name mentioned in free text."""
    normalized_text = _normalize(text)
    matches: list[tuple[int, str]] = []
    for part in load_pc_parts().get(collection, []):
        for term in _terms(part):
            normalized_term = _normalize(term)
            if normalized_term and normalized_term in normalized_text:
                matches.append((len(normalized_term), part["name"]))
    return max(matches, default=(0, None))[1]


def _resolve_part(collection: str, value: str) -> dict | None:
    normalized_value = _normalize(value)
    candidates: list[tuple[int, dict]] = []
    for part in load_pc_parts().get(collection, []):
        for term in _terms(part):
            normalized_term = _normalize(term)
            if normalized_value == normalized_term:
                return deepcopy(part)
            if normalized_term in normalized_value:
                candidates.append((len(normalized_term), part))
    if not candidates:
        return None
    return deepcopy(max(candidates, key=lambda item: item[0])[1])


def pc_build_compatibility_tool(
    cpu: str | None = None,
    motherboard: str | None = None,
    case: str | None = None,
    gpu: str | None = None,
    cpu_cooler: str | None = None,
    aio_cooler: str | None = None,
    memory: str | None = None,
    psu: str | None = None,
    radiator_position: str | None = None,
    check_mode: str | None = None,
) -> dict:
    """Evaluate only the rules for parts provided by the caller."""
    requested = {
        "cpu": cpu,
        "motherboard": motherboard,
        "case": case,
        "gpu": gpu,
        "cpu_cooler": cpu_cooler,
        "aio_cooler": aio_cooler,
        "memory": memory,
        "psu": psu,
    }
    resolved: dict[str, dict] = {}
    hard_conflicts: list[str] = []
    warnings: list[str] = []
    warning_details: list[dict[str, str]] = []
    suggestions: list[str] = []
    checked_items: list[dict[str, str]] = []
    unknown_parts: list[str] = []
    missing_info: list[str] = []

    def check(rule: str, result: str, summary: str) -> None:
        checked_items.append({"rule": rule, "result": result, "summary": summary})

    def warn(warning_type: str, rule: str, message: str) -> None:
        warnings.append(message)
        warning_details.append({"type": warning_type, "rule": rule, "message": message})
        check(rule, "warning", message)

    def missing(field: str, rule: str, message: str) -> None:
        if field not in missing_info:
            missing_info.append(field)
        if not any(item["rule"] == rule and item["message"] == message for item in warning_details):
            warnings.append(message)
            warning_details.append(
                {"type": "data_missing", "rule": rule, "message": message}
            )
            check(rule, "unknown", message)

    for key, value in requested.items():
        if not value:
            continue
        part = _resolve_part(INPUT_TO_COLLECTION[key], value)
        if part is None:
            summary = f"本地规格数据暂未收录{PART_LABELS[key]}“{value}”"
            unknown_parts.append(summary)
            warnings.append(summary)
            warning_details.append(
                {"type": "data_missing", "rule": f"{key}_data", "message": summary}
            )
            check(f"{key}_data", "unknown", summary)
        else:
            resolved[key] = part

    cpu_part = resolved.get("cpu")
    board = resolved.get("motherboard")
    pc_case = resolved.get("case")
    gpu_part = resolved.get("gpu")
    cooler = resolved.get("aio_cooler") or resolved.get("cpu_cooler")
    ram = resolved.get("memory")
    power = resolved.get("psu")

    if cpu_part and board:
        if cpu_part["socket"] != board["socket"]:
            reason = (
                f"{cpu_part['name']} 是 {cpu_part['socket']} 插槽，"
                f"{board['name']} 是 {board['socket']} 插槽，物理上无法安装"
            )
            hard_conflicts.append(reason)
            check("cpu_motherboard_socket", "no", reason)
        else:
            summary = f"CPU 与主板插槽一致，都是 {cpu_part['socket']}"
            check("cpu_motherboard_socket", "yes", summary)
            if board["chipset"] not in cpu_part.get("recommended_chipsets", []):
                warning = (
                    f"{board['chipset']} 不在 {cpu_part['name']} 的本地推荐芯片组列表中，"
                    "需要再核对官方 CPU 支持列表和 BIOS 版本"
                )
                warn("specification", "cpu_chipset_recommendation", warning)

    if board and pc_case:
        if board["form_factor"] not in pc_case["supported_motherboard"]:
            reason = (
                f"{pc_case['name']} 不支持 {board['form_factor']} 主板，"
                f"其支持规格为 {', '.join(pc_case['supported_motherboard'])}"
            )
            hard_conflicts.append(reason)
            check("motherboard_case_form_factor", "no", reason)
        else:
            summary = f"{pc_case['name']} 支持 {board['form_factor']} 主板安装"
            check("motherboard_case_form_factor", "yes", summary)
            if pc_case.get("size_class") == "ATX" and board["form_factor"] == "M-ATX":
                warning = (
                    "ATX 大机箱可以安装 M-ATX 主板，物理兼容，"
                    "但视觉上可能显得主板下方空间较空"
                )
                warn("aesthetic", "matx_board_atx_case_aesthetics", warning)

    if gpu_part and pc_case:
        clearance = pc_case["max_gpu_length_mm"] - gpu_part["length_mm"]
        if clearance < 0:
            reason = (
                f"显卡长 {gpu_part['length_mm']}mm，超过机箱上限 "
                f"{pc_case['max_gpu_length_mm']}mm，超出 {-clearance}mm"
            )
            hard_conflicts.append(reason)
            check("gpu_length_clearance", "no", reason)
        elif clearance <= 10:
            warning = (
                f"显卡距离机箱长度上限只剩 {clearance}mm，安装走线、前置风扇或冷排后可能空间不足"
            )
            warn("clearance", "gpu_length_clearance", warning)
        else:
            check("gpu_length_clearance", "yes", f"显卡长度仍有 {clearance}mm 余量")

        if gpu_part["slot_width"] >= 3 and pc_case.get("bottom_fan_support"):
            warning = (
                f"显卡厚度为 {gpu_part['slot_width']} 槽，机箱又支持底部风扇，"
                "显卡与底部风扇之间可能过近，可能压缩进风空间并影响底部进风效果，"
                "需核对实际槽位和风扇厚度"
            )
            warn("clearance", "gpu_bottom_fan_risk", warning)

    if cooler and cooler.get("type") == "air" and pc_case:
        cooler_height = cooler.get("height_mm")
        case_height = pc_case.get("max_cpu_cooler_height_mm")
        if cooler_height is None:
            missing("cpu_cooler.height_mm", "cooler_case_height", "缺少风冷散热器高度，无法判断是否超高")
        elif case_height is None:
            missing("case.max_cpu_cooler_height_mm", "cooler_case_height", "缺少机箱风冷限高，无法判断是否超高")
        else:
            clearance = case_height - cooler_height
            if clearance < 0:
                reason = (
                    f"风冷高 {cooler_height}mm，超过机箱限高 "
                    f"{case_height}mm"
                )
                hard_conflicts.append(reason)
                check("cooler_case_height", "no", reason)
            elif clearance <= 5:
                warning = f"风冷距离机箱限高只剩 {clearance}mm，侧板公差可能让安装偏紧"
                warn("clearance", "cooler_case_height", warning)
            else:
                check("cooler_case_height", "yes", f"风冷高度仍有 {clearance}mm 余量")

    if cooler and cooler.get("type") == "air" and not pc_case and (
        check_mode == "cooler_case_height" or not ram
    ):
        missing("case", "cooler_case_height", "缺少机箱型号，无法核对风冷限高")

    if cooler and cooler.get("type") == "liquid":
        radiator_size = cooler.get("radiator_size_mm")
        if not pc_case:
            missing("case", "radiator_case_support", "缺少机箱型号，无法核对冷排安装位置")
        elif not radiator_size:
            missing(
                "aio_cooler.radiator_size_mm",
                "radiator_case_support",
                "缺少水冷冷排尺寸，无法判断机箱是否支持",
            )
        else:
            support_fields = {
                "top": ("top_radiator_support_mm", "top_radiator_support"),
                "front": ("front_radiator_support_mm", "front_radiator_support"),
                "side": ("side_radiator_support_mm", "side_radiator_support"),
            }
            support_data_available = any(
                new_key in pc_case or legacy_key in pc_case
                for new_key, legacy_key in support_fields.values()
            )
            supported_positions = [
                position
                for position, (new_key, legacy_key) in support_fields.items()
                if radiator_size
                in (pc_case.get(new_key) or pc_case.get(legacy_key) or [])
            ]
            position_labels = {"top": "顶部", "front": "前部", "side": "侧面"}
            if not support_data_available:
                missing(
                    "case.radiator_support_mm",
                    "radiator_case_support",
                    "机箱缺少冷排尺寸支持数据，无法确认安装位置",
                )
            elif not supported_positions:
                reason = f"机箱已记录的顶部、前部和侧面位置均不支持 {radiator_size}mm 冷排"
                hard_conflicts.append(reason)
                check("radiator_case_support", "no", reason)
            elif radiator_position and radiator_position not in supported_positions:
                supported_text = "、".join(position_labels[item] for item in supported_positions)
                warn(
                    "placement",
                    "radiator_case_support",
                    f"{radiator_size}mm 冷排仅确认可装在{supported_text}，未确认支持"
                    f"{position_labels.get(radiator_position, radiator_position)}安装",
                )
            elif len(supported_positions) == 1 and not radiator_position:
                supported_text = position_labels[supported_positions[0]]
                warn(
                    "placement",
                    "radiator_case_support",
                    f"机箱支持 {radiator_size}mm 冷排，但已知安装位置仅限{supported_text}",
                )
            else:
                check(
                    "radiator_case_support",
                    "yes",
                    f"机箱支持 {radiator_size}mm 冷排，已确认位置："
                    + "、".join(position_labels[item] for item in supported_positions),
                )

            if radiator_position == "front" and gpu_part:
                front_gpu_limit = pc_case.get("max_gpu_length_with_front_radiator_mm")
                gpu_length = gpu_part.get("length_mm")
                if front_gpu_limit is None:
                    missing(
                        "case.max_gpu_length_with_front_radiator_mm",
                        "front_radiator_gpu_clearance",
                        "机箱缺少安装前置冷排后的显卡限长，需查官方结构图确认",
                    )
                elif gpu_length is None:
                    missing(
                        "gpu.length_mm",
                        "front_radiator_gpu_clearance",
                        "缺少显卡长度，无法核对前置冷排后的剩余空间",
                    )
                else:
                    clearance = front_gpu_limit - gpu_length
                    if clearance < 0:
                        reason = (
                            f"前置冷排安装后显卡限长为 {front_gpu_limit}mm，"
                            f"显卡长 {gpu_length}mm，超出 {-clearance}mm"
                        )
                        hard_conflicts.append(reason)
                        check("front_radiator_gpu_clearance", "no", reason)
                    elif clearance < 10:
                        warn(
                            "clearance",
                            "front_radiator_gpu_clearance",
                            f"前置冷排安装后显卡长度余量仅 {clearance}mm",
                        )
                    else:
                        check(
                            "front_radiator_gpu_clearance",
                            "yes",
                            f"前置冷排安装后显卡长度仍有 {clearance}mm 余量",
                        )
            elif radiator_position == "front" and check_mode == "front_radiator_gpu_clearance":
                missing("gpu", "front_radiator_gpu_clearance", "缺少显卡型号或长度，无法判断前置冷排是否挡显卡")

            radiator_thickness = cooler.get("radiator_thickness_mm")
            fan_thickness = cooler.get("fan_thickness_mm")
            thickness_clearance = pc_case.get("radiator_thickness_clearance_mm")
            if radiator_thickness is None:
                missing(
                    "aio_cooler.radiator_thickness_mm",
                    "radiator_thickness_clearance",
                    "缺少冷排厚度，需要核对水冷规格",
                )
            if fan_thickness is None:
                missing(
                    "aio_cooler.fan_thickness_mm",
                    "radiator_thickness_clearance",
                    "缺少冷排风扇厚度，需要核对水冷规格",
                )
            if thickness_clearance is None:
                missing(
                    "case.radiator_thickness_clearance_mm",
                    "radiator_thickness_clearance",
                    "机箱缺少冷排加风扇厚度余量，需要核对官方结构尺寸",
                )
            if (
                radiator_thickness is not None
                and fan_thickness is not None
                and thickness_clearance is not None
            ):
                installed_thickness = radiator_thickness + fan_thickness
                remaining = thickness_clearance - installed_thickness
                if remaining < 5:
                    warn(
                        "clearance",
                        "radiator_thickness_clearance",
                        f"冷排加风扇厚度为 {installed_thickness}mm，机箱厚度余量仅 {remaining}mm",
                    )
                else:
                    check(
                        "radiator_thickness_clearance",
                        "yes",
                        f"冷排加风扇厚度仍有 {remaining}mm 余量",
                    )

            if radiator_position == "top":
                warn(
                    "clearance",
                    "top_radiator_clearance",
                    "顶部冷排仍可能与主板 VRM、内存马甲或机箱上沿冲突，需核对主板区域净空",
                )

    if cooler and cooler.get("type") == "air" and ram:
        cooler_ram_clearance = cooler.get("ram_clearance_mm")
        ram_height = ram.get("height_mm")
        if cooler_ram_clearance is None:
            missing(
                "cpu_cooler.ram_clearance_mm",
                "cooler_memory_clearance",
                "散热器缺少内存避让高度，无法确认双塔风冷与高马甲内存间距",
            )
        elif ram_height is None:
            missing(
                "memory.height_mm",
                "cooler_memory_clearance",
                "缺少内存高度，无法确认是否与风冷散热器冲突",
            )
        elif cooler_ram_clearance < ram_height:
            warning = (
                f"散热器内存避让高度 {cooler_ram_clearance}mm，"
                f"小于内存高度 {ram_height}mm，前风扇或鳍片可能挡高马甲内存"
            )
            warn("clearance", "cooler_memory_clearance", warning)
        else:
            check(
                "cooler_memory_clearance",
                "yes",
                f"散热器内存避让高度可覆盖 {ram_height}mm 内存",
            )

    if board and ram:
        if board["memory_type"] != ram["memory_type"]:
            reason = (
                f"主板使用 {board['memory_type']}，内存是 {ram['memory_type']}，"
                "代际和防呆口不同，无法安装"
            )
            hard_conflicts.append(reason)
            check("motherboard_memory_type", "no", reason)
        else:
            check("motherboard_memory_type", "yes", f"主板与内存均为 {ram['memory_type']}")

    if gpu_part and power:
        deficit = gpu_part["recommended_psu_w"] - power["wattage"]
        if deficit >= 100:
            reason = (
                f"电源只有 {power['wattage']}W，比显卡建议的 "
                f"{gpu_part['recommended_psu_w']}W 低 {deficit}W，供电余量明显不足"
            )
            hard_conflicts.append(reason)
            check("psu_gpu_wattage", "no", reason)
        elif deficit > 0:
            warning = (
                f"电源比显卡建议功率低 {deficit}W，高负载时余量偏小，建议升级到"
                f"至少 {gpu_part['recommended_psu_w']}W"
            )
            warn("power", "psu_gpu_wattage", warning)
        else:
            check(
                "psu_gpu_wattage",
                "yes",
                f"电源达到显卡建议的 {gpu_part['recommended_psu_w']}W",
            )

    if power and pc_case:
        clearance = pc_case["psu_max_length_mm"] - power["length_mm"]
        if clearance < 0:
            reason = (
                f"电源长 {power['length_mm']}mm，超过机箱电源限长 "
                f"{pc_case['psu_max_length_mm']}mm"
            )
            hard_conflicts.append(reason)
            check("psu_case_length", "no", reason)
        elif clearance <= 10:
            warning = f"电源仓只剩 {clearance}mm 余量，模组线材弯折空间可能不足"
            warn("clearance", "psu_case_length", warning)
        else:
            check("psu_case_length", "yes", f"电源长度仍有 {clearance}mm 余量")

    if unknown_parts:
        suggestions.extend(unknown_parts)
        suggestions.append("请提供完整品牌型号或产品规格页，数据缺失部分不能直接判断兼容")
        for key, value in requested.items():
            if value and key not in resolved:
                field = key
                if field not in missing_info:
                    missing_info.append(field)
    if not any(requested.values()):
        message = "缺少关键型号或规格信息，AI 无法可靠判断"
        warnings.append(message)
        warning_details.append(
            {"type": "data_missing", "rule": "required_parts", "message": message}
        )
        suggestions.append("请至少提供两个需要搭配的部件型号，例如 CPU 和主板、显卡和机箱")
    elif not checked_items:
        message = "当前信息不足，尚未形成可检查的部件搭配关系"
        warnings.append(message)
        warning_details.append(
            {"type": "data_missing", "rule": "required_pair", "message": message}
        )
        suggestions.append("请补充与当前部件搭配的另一个部件完整型号")

    warning_types = list(dict.fromkeys(item["type"] for item in warning_details))
    if "aesthetic" in warning_types:
        suggestions.append("在意紧凑协调可选 M-ATX 机箱；若已经拥有 ATX 机箱，也可以继续使用")
    if "clearance" in warning_types:
        suggestions.append("尺寸类风险建议额外预留走线、风扇和安装公差，不要只看纸面极限值")
    if "power" in warning_types:
        suggestions.append("供电风险还应核对显卡供电接口数量和电源线材规格")
    if "specification" in warning_types:
        suggestions.append("规格类风险建议以主板或配件厂商的官方支持列表为准")
    if "placement" in warning_types:
        suggestions.append("冷排位置受限时应按机箱官方安装图选择顶部、前部或侧面位置")
    if missing_info:
        suggestions.append("请补充：" + "、".join(missing_info))
    if hard_conflicts:
        suggestions.append("存在硬冲突时不要强行安装，优先更换对应部件")

    if hard_conflicts:
        compatible, risk_level = "no", "high"
    elif "data_missing" in warning_types:
        compatible, risk_level = "unknown", "unknown"
    elif warnings:
        compatible, risk_level = "warning", "medium"
    else:
        compatible, risk_level = "yes", "low"

    return {
        "compatible": compatible,
        "risk_level": risk_level,
        "hard_conflicts": hard_conflicts,
        "warnings": warnings,
        "warning_types": warning_types,
        "warning_details": warning_details,
        "suggestions": list(dict.fromkeys(suggestions)),
        "checked_items": checked_items,
        "missing_info": missing_info,
    }
