"""Agent for small, local, structured hardware tool calls."""

import re

from app.tools.hardware_tools import hardware_spec_tool
from app.tools.pc_build_tools import find_pc_part_name, pc_build_compatibility_tool
from app.services.rag_service import rag_service
from app.services.source_policy import (
    COMMUNITY_EXPERIENCE_SOURCE_TYPE,
    apply_source_policy,
    source_label,
)


class ToolAgent:
    """Select a supported tool, extract simple entities, and format its result."""

    # Do not use ``\b`` here: ASCII model names are commonly adjacent to
    # Chinese characters, and both are treated as word characters by Python.
    CPU_PATTERN = re.compile(r"(?i)(?:Ryzen\s*)?\d{4,5}[A-Z]{0,3}|Ryzen\s*\d{4}")
    MOTHERBOARD_PATTERN = re.compile(r"(?i)B850M|B850|Z790|H610M")
    COMPATIBILITY_WORDS = (
        "搭配",
        "兼容",
        "可以配",
        "能配",
        "是否支持",
        "支持",
        "能不能用",
        "能用",
        "可以用",
        "可以安装",
        "是否匹配",
        "匹配",
        "能不能装",
        "能装",
        "装前面",
        "装顶部",
        "会不会太长",
        "会不会挡",
        "会不会顶",
        "会不会超高",
        "挡底部风扇",
        "挡内存",
        "前置冷排",
        "影响显卡长度",
        "顶部冷排",
        "冷排",
        "适合水冷",
        "还是风冷",
        "顶部好",
        "前面好",
        "余量",
        "够吗",
        "电源够不够",
        "瓦数够不够",
        "不好看",
        "走线难",
        "机箱风道",
        "风道要注意",
        "这套配置",
        "装机",
    )
    SPEC_WORDS = ("规格", "参数", "内存类型", "什么内存")
    PART_COLLECTIONS = {
        "cpu": "cpus",
        "motherboard": "motherboards",
        "case": "cases",
        "gpu": "gpus",
        "memory": "memory",
        "psu": "psus",
    }
    OVERALL_BUILD_WORDS = ("这套配置", "整套配置", "整体兼容", "整机兼容")
    GPU_LENGTH_WORDS = ("会不会太长", "显卡太长", "显卡长度", "显卡限长", "能不能装进", "最大支持")
    GPU_BOTTOM_FAN_WORDS = ("底部风扇", "底部进风", "厚显卡")
    RADIATOR_SUPPORT_WORDS = ("能装", "支持", "装得下")
    FRONT_RADIATOR_GPU_WORDS = ("前置冷排", "装前面", "前面", "挡显卡", "影响显卡长度")
    TOP_RADIATOR_WORDS = ("顶部冷排", "装顶部", "顶部", "顶内存", "顶主板", "vrm")
    AIR_HEIGHT_WORDS = ("风冷", "超高", "限高")
    COOLER_MEMORY_WORDS = ("双塔", "挡内存", "高马甲内存")
    COOLING_ADVICE_WORDS = ("适合水冷还是风冷", "水冷还是风冷", "顶部好还是前面好", "顶部好", "前面好")
    GPU_SLOT_PATTERN = re.compile(r"(?i)\d+(?:\.\d+)?\s*槽")
    COMMUNITY_EXPERIENCE_WORDS = (
        "m-atx",
        "matx",
        "atx 机箱",
        "不好看",
        "厚显卡",
        "底部风扇",
        "前置冷排",
        "360 冷排",
        "360冷排",
        "顶部水冷",
        "顶部冷排",
        "顶内存",
        "双塔风冷",
        "高马甲内存",
        "小机箱",
        "走线",
        "海景房",
        "风道",
    )

    def __init__(self, retriever=None) -> None:
        self.retriever = retriever

    def run(self, query: str) -> dict:
        """Execute one supported local tool for *query*."""
        motherboard = self._extract(self.MOTHERBOARD_PATTERN, query)

        if self._contains_any(query, self.COMPATIBILITY_WORDS):
            tool_input = self._pc_build_input(query)
            primary_check = self._primary_check(query)
            if primary_check != "overall_compatibility":
                tool_input["check_mode"] = primary_check
            tool_result = pc_build_compatibility_tool(**tool_input)
            primary_warning = next(
                (
                    item for item in tool_result.get("warning_details", [])
                    if item.get("rule") == primary_check
                ),
                None,
            )
            tool_result["primary_check"] = primary_check
            tool_result["primary_warning"] = primary_warning
            result = {
                "query": query,
                "tool_name": "pc_build_compatibility_tool",
                "tool_input": tool_input,
                "tool_result": tool_result,
                "answer": self._pc_build_answer(tool_result),
                "sources": [],
            }
            return self._with_community_experience(query, result)

        product = motherboard
        if product and self._contains_any(query, self.SPEC_WORDS):
            tool_input = {"product": product}
            tool_result = hardware_spec_tool(**tool_input)
            return {
                "query": query,
                "tool_name": "hardware_spec_tool",
                "tool_input": tool_input,
                "tool_result": tool_result,
                "answer": self._spec_answer(product, tool_result),
                "sources": [],
            }

        return {
            "query": query,
            "tool_name": None,
            "tool_input": {},
            "tool_result": {
                "status": "unknown",
                "reason": "当前本地工具无法识别可执行的结构化查询。",
            },
            "answer": "当前本地工具暂时无法处理这个问题。",
            "sources": [],
        }

    def _with_community_experience(self, query: str, result: dict) -> dict:
        """Keep the tool conclusion primary and add community context as a hint."""
        if self.retriever is None or not self._contains_any(
            query, self.COMMUNITY_EXPERIENCE_WORDS
        ):
            return result
        try:
            contexts = [
                item
                for item in self.retriever.search(query, top_k=5)
                if item.get("source_type") == COMMUNITY_EXPERIENCE_SOURCE_TYPE
            ][:1]
        except Exception:
            # Community hints are supplementary and must never make the
            # deterministic compatibility tool unavailable.
            return result
        if not contexts:
            return result

        excerpts = []
        sources = []
        for context in contexts:
            content = re.sub(r"\s+", " ", str(context.get("content") or "")).strip()
            if content:
                excerpts.append(content[:320])
            source_type = str(context.get("source_type") or "")
            sources.append(
                {
                    "filename": str(context.get("filename") or ""),
                    "page_number": context.get("page_number"),
                    "section_title": str(context.get("section_title") or ""),
                    "source_type": source_type,
                    "source_label": context.get("source_label")
                    or source_label(source_type),
                }
            )
        if excerpts:
            result["answer"] = (
                f"{result['answer']}\n\n社区经验补充："
                + "\n".join(excerpts)
            )
        result["answer"] = apply_source_policy(result["answer"], contexts)
        result["sources"] = sources
        return result

    @staticmethod
    def _extract(pattern: re.Pattern, query: str) -> str | None:
        match = pattern.search(query)
        return match.group(0).upper() if match else None

    @staticmethod
    def _contains_any(query: str, words: tuple[str, ...]) -> bool:
        normalized = query.casefold()
        return any(word.casefold() in normalized for word in words)

    @classmethod
    def _primary_check(cls, query: str) -> str:
        if cls._contains_any(query, cls.OVERALL_BUILD_WORDS):
            return "overall_compatibility"
        if cls._contains_any(query, cls.COOLING_ADVICE_WORDS):
            return "cooling_configuration_advice"
        if cls._contains_any(query, cls.FRONT_RADIATOR_GPU_WORDS) and cls._contains_any(
            query, ("显卡", "gpu")
        ):
            return "front_radiator_gpu_clearance"
        if cls._contains_any(query, cls.TOP_RADIATOR_WORDS):
            return "top_radiator_clearance"
        if cls._contains_any(query, cls.COOLER_MEMORY_WORDS):
            return "cooler_memory_clearance"
        if cls._contains_any(query, cls.AIR_HEIGHT_WORDS) and "风冷" in query:
            return "cooler_case_height"
        if cls._contains_any(query, ("水冷", "冷排")) and cls._contains_any(
            query, cls.RADIATOR_SUPPORT_WORDS
        ):
            return "radiator_case_support"
        if cls._contains_any(query, cls.GPU_LENGTH_WORDS):
            return "gpu_length_clearance"
        if (
            cls._contains_any(query, cls.GPU_BOTTOM_FAN_WORDS)
            or cls.GPU_SLOT_PATTERN.search(query)
        ):
            return "gpu_bottom_fan_risk"
        return "overall_compatibility"

    @classmethod
    def _pc_build_input(cls, query: str) -> dict[str, str]:
        tool_input = {
            field: name
            for field, collection in cls.PART_COLLECTIONS.items()
            if (name := find_pc_part_name(collection, query))
        }
        if "cpu" not in tool_input:
            extracted_cpu = cls._extract(cls.CPU_PATTERN, query)
            if extracted_cpu:
                tool_input["cpu"] = extracted_cpu
            elif "未知型号cpu" in query.casefold():
                tool_input["cpu"] = "未知型号CPU"
        if "motherboard" not in tool_input:
            extracted_board = cls._extract(cls.MOTHERBOARD_PATTERN, query)
            if extracted_board:
                tool_input["motherboard"] = extracted_board
        normalized = query.casefold()
        if "水冷" in normalized or "冷排" in normalized:
            aio_name = find_pc_part_name("aio_coolers", query)
            tool_input["aio_cooler"] = aio_name or "未提供水冷型号或尺寸"
        elif "风冷" in normalized or "散热器" in normalized:
            cooler_name = find_pc_part_name("cpu_coolers", query)
            tool_input["cpu_cooler"] = cooler_name or "未提供风冷散热器型号"
        if "机箱" in normalized and "case" not in tool_input:
            tool_input["case"] = "未提供机箱型号"
        if "显卡" in normalized and "gpu" not in tool_input:
            tool_input["gpu"] = "未提供显卡型号"
        if "内存" in normalized and "memory" not in tool_input:
            tool_input["memory"] = "未提供内存型号或高度"
        mentions_front = cls._contains_any(query, ("前置", "前面", "前部"))
        mentions_top = cls._contains_any(query, ("顶部", "顶置", "上方"))
        if mentions_front and not mentions_top:
            tool_input["radiator_position"] = "front"
        elif mentions_top and not mentions_front:
            tool_input["radiator_position"] = "top"
        elif cls._contains_any(query, ("侧面", "侧置")):
            tool_input["radiator_position"] = "side"
        return tool_input

    @staticmethod
    def _spec_answer(product: str, result: dict) -> str:
        if result.get("status") == "unknown":
            return result["reason"]
        series = "/".join(item.removeprefix("AMD Ryzen ") for item in result["cpu_support"])
        return (
            f"{product}主板采用{result['socket']}插槽，支持AMD Ryzen {series}系列处理器，"
            f"并支持{result['memory_type']}内存。"
        )

    @staticmethod
    def _pc_build_answer(result: dict) -> str:
        warning_types = set(result.get("warning_types", []))
        primary_check = result.get("primary_check", "overall_compatibility")
        primary_warning = result.get("primary_warning")
        if result["compatible"] == "warning" and primary_check == "gpu_bottom_fan_risk" and primary_warning:
            conclusion = (
                "结论：厚显卡可能与底部风扇距离过近，并影响底部进风，"
                "需要核对实际安装空间。"
            )
        elif result["compatible"] == "warning" and primary_check == "gpu_length_clearance" and primary_warning:
            conclusion = "结论：显卡长度接近机箱上限，需要确认风扇、冷排和走线是否占用空间。"
        elif result["compatible"] == "warning" and warning_types == {"aesthetic"}:
            conclusion = "结论：可以正常安装，物理兼容；需要注意机箱内部留白和外观协调。"
        else:
            conclusion = {
                "yes": "结论：这套搭配在已检查项目中兼容，可以按当前方向装机。",
                "warning": "结论：已检查项目可以搭配，但存在需要提前确认的具体风险。",
                "no": "结论：当前配置存在硬冲突，不建议直接购买或强行安装。",
                "unknown": "结论：信息不足，暂时无法判断兼容性，不能靠猜测下结论。",
            }[result["compatible"]]
        lines = [conclusion]
        confirmed = [
            item["summary"] for item in result["checked_items"] if item["result"] == "yes"
        ]
        if confirmed:
            lines.append("确定兼容：" + "；".join(confirmed))
        if result["hard_conflicts"]:
            lines.append("不兼容原因：" + "；".join(result["hard_conflicts"]))
        if result["warnings"]:
            if primary_check == "overall_compatibility" or not primary_warning:
                lines.append("需要注意：" + "；".join(result["warnings"]))
            else:
                lines.append("重点回答：" + primary_warning["message"])
                other_warnings = [
                    item["message"]
                    for item in result.get("warning_details", [])
                    if item.get("rule") != primary_check
                ]
                if other_warnings:
                    lines.append("另外还需注意：" + "；".join(other_warnings))
        if result["suggestions"]:
            lines.append("小白更稳的选择：" + "；".join(result["suggestions"]))
        return "\n".join(lines)


tool_agent = ToolAgent(retriever=rag_service)
