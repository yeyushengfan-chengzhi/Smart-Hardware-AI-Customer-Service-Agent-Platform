"""Minimal rule-and-knowledge based hardware diagnosis agent."""

from dataclasses import dataclass
from typing import Protocol

from app.services.rag_service import RAGSearchResult, rag_service
from app.services.source_policy import source_label


class KnowledgeRetriever(Protocol):
    def search(self, query: str, top_k: int) -> list[RAGSearchResult]: ...


@dataclass(frozen=True)
class StepTemplate:
    action: str
    reason: str
    search_query: str


class DiagnosisAgent:
    """Classify a hardware fault, plan checks, and ground each check in RAG."""

    DEVICE_KEYWORDS = {
        "motherboard": ("主板", "motherboard"),
        "gpu": ("显卡", "gpu", "graphics card", "video card"),
        "memory": ("内存", "memory", "dram", "dimm"),
        "power": ("电源", "power supply", "psu"),
        "monitor": ("显示器", "monitor", "screen"),
    }
    FAULT_KEYWORDS = {
        "no_display": ("无显示", "没有显示", "黑屏", "无画面", "no display"),
        "boot_failure": ("无法启动", "无法开机", "启动失败", "开不了机", "boot failure"),
        "overheating": ("过热", "高温", "温度异常", "overheating"),
        "installation_error": ("安装", "插槽", "未检测", "检测不到", "无法检测", "installation"),
        "hardware_error": ("故障", "异常", "报错", "错误", "故障灯", "error"),
    }

    COMMON_PLANS = {
        "no_display": (
            StepTemplate("检查 EZ Debug LED 状态", "LED 可定位 CPU、DRAM、GPU 或启动设备异常", "EZ Debug LED CPU DRAM GPU 故障灯"),
            StepTemplate("检查 CPU 供电和安装", "CPU 未正确供电或安装会阻止 POST", "CPU 供电 安装 POST 无显示"),
            StepTemplate("检查 DRAM 内存安装状态", "DRAM 未插紧或训练失败可能导致无显示", "DRAM DIMM 安装 无显示"),
            StepTemplate("检查 GPU 和显示输出", "显卡、线缆或输出端口异常会导致无画面", "GPU 显卡 HDMI DisplayPort 显示输出"),
            StepTemplate("尝试清除 CMOS", "恢复 BIOS 默认设置可排除错误配置", "清除 CMOS 恢复 BIOS 默认设置"),
        ),
        "boot_failure": (
            StepTemplate("检查主电源和 CPU 供电", "供电连接异常会导致系统无法启动", "ATX CPU 电源 供电 无法启动"),
            StepTemplate("检查启动诊断灯或蜂鸣码", "诊断指示可缩小故障范围", "Debug LED 蜂鸣码 POST 启动故障"),
            StepTemplate("最小化硬件配置后重试", "移除非必要设备可隔离故障部件", "最小系统 启动故障 排查"),
        ),
        "overheating": (
            StepTemplate("检查散热器和风扇", "散热器接触或风扇异常会造成温度升高", "散热器 风扇 温度异常"),
            StepTemplate("检查风道和灰尘", "风道受阻会降低散热能力", "机箱 风道 灰尘 过热"),
            StepTemplate("检查 BIOS 温度和风扇设置", "监控数据可确认温度与转速异常", "BIOS 温度 风扇转速"),
        ),
        "hardware_error": (
            StepTemplate("读取诊断灯或错误码", "错误指示可定位异常硬件", "硬件 错误码 Debug LED 故障灯"),
            StepTemplate("重新安装并检查相关硬件", "接触不良是常见硬件异常原因", "硬件 重新安装 接触不良"),
            StepTemplate("使用最小配置交叉检查", "逐项替换可以隔离故障部件", "最小配置 交叉测试 硬件故障"),
        ),
        "installation_error": (
            StepTemplate("确认插槽和接口兼容性", "错误的插槽或接口会导致设备无法识别", "硬件 插槽 接口 兼容 安装"),
            StepTemplate("重新安装设备并检查连接", "未完全插入或线缆松动会造成检测失败", "重新安装 连接 检测不到"),
            StepTemplate("在 BIOS 或系统中检查设备检测状态", "检测状态可区分安装与驱动问题", "BIOS 设备检测 安装"),
        ),
    }
    DEVICE_STEPS = {
        "gpu": (
            StepTemplate("检查 PCIe 插槽和显卡供电", "PCIe 接触或辅助供电异常会使 GPU 无法检测", "PCIe GPU 显卡供电 无法检测"),
            StepTemplate("检查 BIOS 和系统中的 GPU 检测状态", "检测状态可定位固件、插槽或设备问题", "BIOS GPU 检测 显卡 未识别"),
            StepTemplate("检查显示输出连接", "输出端口、线缆或输入源错误会导致无显示", "GPU HDMI DisplayPort 显示输出"),
        ),
        "memory": (
            StepTemplate("检查 DRAM 故障灯", "DRAM 指示灯可确认内存初始化异常", "DRAM 故障灯 内存错误"),
            StepTemplate("按说明书重新安装 DIMM", "DIMM 插槽顺序或接触不良会导致训练失败", "DIMM 插槽 顺序 重新安装"),
        ),
    }

    def __init__(self, retriever: KnowledgeRetriever = rag_service, sources_per_step: int = 3) -> None:
        self.retriever = retriever
        self.sources_per_step = sources_per_step

    def diagnose(self, query: str, device_type: str = "unknown", fault_type: str = "unknown") -> dict:
        device = self._normalize_device(device_type) or self._match(query, self.DEVICE_KEYWORDS) or "unknown"
        fault = self._normalize_fault(fault_type) or self._match(query, self.FAULT_KEYWORDS) or "hardware_error"
        templates = self._plan(device, fault)
        steps = []
        for template in templates:
            contexts = self.retriever.search(f"{query} {template.search_query}", top_k=self.sources_per_step)
            sources = [
                {
                    "filename": item["filename"],
                    "page_number": item["page_number"],
                    "section_title": item["section_title"],
                    "source_type": item.get("source_type", ""),
                    "source_label": item.get("source_label")
                    or source_label(item.get("source_type", "")),
                }
                for item in contexts
            ]
            steps.append({"action": template.action, "reason": template.reason, "sources": sources})
        return {"query": query, "device": device, "fault_type": fault, "steps": steps}

    def _plan(self, device: str, fault: str) -> tuple[StepTemplate, ...]:
        device_steps = self.DEVICE_STEPS.get(device, ())
        base_steps = self.COMMON_PLANS.get(fault, self.COMMON_PLANS["hardware_error"])
        if device in {"gpu", "memory"}:
            return device_steps
        return base_steps

    @classmethod
    def _match(cls, query: str, groups: dict[str, tuple[str, ...]]) -> str | None:
        normalized = query.casefold()
        return next((name for name, words in groups.items() if any(word in normalized for word in words)), None)

    @staticmethod
    def _normalize_device(value: str) -> str | None:
        return {"power_supply": "power"}.get(value, value) if value not in {"", "unknown"} else None

    @staticmethod
    def _normalize_fault(value: str) -> str | None:
        aliases = {"boot_failed": "boot_failure", "memory_error": "hardware_error", "gpu_error": "hardware_error", "power_issue": "hardware_error", "cmos_reset": "hardware_error"}
        return aliases.get(value, value) if value not in {"", "unknown"} else None


diagnosis_agent = DiagnosisAgent()
