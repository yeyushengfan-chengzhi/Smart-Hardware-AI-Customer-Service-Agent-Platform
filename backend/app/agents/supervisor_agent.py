"""Rule-based supervisor for intent classification and routing."""

import re


class SupervisorAgent:
    """Classify a query without executing the destination agent."""

    ROUTES = {
        "fault_diagnosis": "diagnosis",
        "compatibility_check": "tool",
        "tool_call": "tool",
        "product_info": "knowledge",
        "after_sales": "AfterSalesAgent",
        "unknown": "GeneralAgent",
    }

    DEVICE_KEYWORDS = {
        "motherboard": ("主板", "motherboard", "b850", "b650", "x870", "x670", "z890", "z790"),
        "gpu": ("显卡", "gpu", "video"),
        "memory": ("内存", "dram", "dimm"),
        "storage": ("硬盘", "固态", "m.2", "ssd", "hdd"),
        "power_supply": ("电源", "power supply", "psu"),
        "monitor": ("显示器", "monitor", "screen"),
        "case": ("机箱", "case"),
        "cooler": ("散热器", "风冷", "水冷", "cooler"),
    }

    FAULT_KEYWORDS = {
        "no_display": ("无显示", "没有显示", "黑屏", "没有画面", "显示器", "display"),
        "boot_failed": (
            "无法开机",
            "无法启动",
            "启动失败",
            "开机失败",
            "开不了机",
            "开机",
            "启动",
            "post",
        ),
        "memory_error": ("内存报错", "内存错误", "dram灯", "dram 灯", "memory error"),
        "gpu_error": ("显卡报错", "显卡错误", "gpu报错", "gpu错误", "video error"),
        "power_issue": ("电源问题", "供电问题", "不通电", "断电", "power issue"),
        "cmos_reset": ("cmos", "bios重置", "bios 重置"),
    }

    AFTER_SALES_KEYWORDS = ("保修", "售后", "维修", "退换")
    PRODUCT_INFO_KEYWORDS = (
        "支持",
        "支持什么",
        "是否支持",
        "可以使用",
        "兼容",
        "参数",
        "规格",
        "接口",
        "插槽",
        "尺寸",
        "功能",
        "说明书",
        "bios",
        "多少",
        "几个",
        "型号",
        "版本",
        "频率",
        "容量",
        "功耗",
        "配置",
        "价格",
    )
    HARDWARE_FAULT_KEYWORDS = (
        "故障",
        "报错",
        "错误",
        "坏了",
        "异常",
        "蓝屏",
        "死机",
        "无法启动",
        "识别不到",
        "检测不到",
        "无法识别",
        "安装失败",
        "不正确",
        "不显示",
        "只识别",
        "打不开",
        "无法启动",
        "无法开机",
        "开机失败",
        "启动失败",
        "无显示",
        "黑屏",
        "没有画面",
        "不通电",
        "断电",
        "cmos",
        "bios重置",
        "bios 重置",
    )
    TOOL_COMPATIBILITY_KEYWORDS = (
        "搭配",
        "兼容",
        "可以配",
        "能配",
        "配吗",
        "能不能用",
        "支持吗",
        "可以用",
        "可以用吗",
        "可以安装吗",
        "可以安装",
        "能装",
        "是否适配",
        "匹配吗",
        "是否匹配",
        "能用吗",
        "能用",
        "compatible",
        "work with",
    )
    TOOL_SPEC_KEYWORDS = ("查询", "规格工具", "硬件规格", "帮我查", "内存类型和插槽规格")
    CPU_REFERENCE_KEYWORDS = ("cpu", "处理器", "ryzen", "锐龙", "未知型号cpu")
    CPU_MODEL_PATTERN = re.compile(r"(?i)(?<![a-z0-9])(?:i[3579]-?)?\d{4,5}[a-z0-9]{0,3}(?![a-z0-9])")
    MOTHERBOARD_KEYWORDS = (
        "主板",
        "motherboard",
        "b850",
        "b650",
        "x870",
        "x670",
        "z890",
        "z790",
    )
    PC_BUILD_QUERY_KEYWORDS = (
        "这套配置",
        "这套配置兼容",
        "整套配置兼容",
        "装机兼容",
        "主板能不能装",
        "机箱能装",
        "机箱支持",
        "能装360水冷",
        "水冷装前面",
        "顶部装水冷",
        "前置冷排",
        "影响显卡长度",
        "顶部冷排",
        "风冷会不会超高",
        "水冷还是风冷",
        "顶部好还是前面好",
        "显卡会不会太长",
        "显卡会不会挡",
        "挡底部风扇",
        "散热器会不会挡",
        "挡高马甲内存",
        "电源够不够",
        "瓦数够不够",
        "大机箱装小板",
        "会不会不好看",
        "装机走线",
        "走线难",
        "机箱风道",
        "风道要注意",
    )
    PC_BUILD_COMPONENT_GROUPS = (
        ("cpu", "处理器", "ryzen", "锐龙", "i7-", "i5-"),
        ("主板", "motherboard", "b850", "b850m", "z790", "h610m"),
        ("机箱", "case"),
        ("显卡", "gpu", "rtx"),
        ("散热器", "风冷", "水冷", "cooler"),
        ("内存", "memory", "ddr4", "ddr5"),
        ("电源", "psu", "w电源"),
    )

    # Secondary semantic rules: a device mention alone is not a fault.  A query
    # is diagnostic when a known device and a problem-state expression coexist.
    # These are reusable language patterns rather than device-specific phrases.
    PROBLEM_STATE_KEYWORDS = (
        "无法检测",
        "检测不到",
        "识别不到",
        "无法识别",
        "不识别",
        "找不到",
        "没有输出",
        "无输出",
        "没有画面",
        "无画面",
        "没有显示",
        "无显示",
        "无信号",
        "不启动",
        "无法启动",
        "启动不了",
        "不能启动",
        "不通电",
        "没反应",
        "not detected",
        "not recognized",
        "no output",
        "no signal",
        "won't boot",
    )

    SEMANTIC_FAULT_TYPES = {
        "no_display": ("没有输出", "无输出", "没有画面", "无画面", "没有显示", "无显示", "无信号", "no output", "no signal"),
        "boot_failed": ("不启动", "无法启动", "启动不了", "不能启动", "不通电", "没反应", "won't boot"),
        "hardware_error": ("无法检测", "检测不到", "识别不到", "无法识别", "不识别", "找不到", "not detected", "not recognized"),
    }

    def route(self, query: str) -> dict[str, str]:
        """Return the classification and destination agent name for *query*."""
        normalized_query = query.strip().lower()
        device_type = self._match(normalized_query, self.DEVICE_KEYWORDS)
        fault_type = self._match(normalized_query, self.FAULT_KEYWORDS)

        semantic_fault = self._is_device_problem(normalized_query, device_type)
        if fault_type == "unknown" and semantic_fault:
            fault_type = self._match(normalized_query, self.SEMANTIC_FAULT_TYPES)

        if self._contains_any(normalized_query, self.AFTER_SALES_KEYWORDS):
            intent = "after_sales"
        elif fault_type != "unknown" or self._contains_any(
            normalized_query, self.HARDWARE_FAULT_KEYWORDS
        ):
            intent = "fault_diagnosis"
        elif semantic_fault:
            intent = "fault_diagnosis"
        elif self._is_compatibility_query(normalized_query):
            intent = "compatibility_check"
        elif self._is_tool_spec_query(normalized_query):
            intent = "tool_call"
        elif self._contains_any(normalized_query, self.PRODUCT_INFO_KEYWORDS):
            intent = "product_info"
        else:
            intent = "unknown"

        return {
            "intent": intent,
            "device_type": device_type,
            "fault_type": fault_type,
            "route": self.ROUTES[intent],
        }

    @classmethod
    def _is_compatibility_query(cls, query: str) -> bool:
        """Recognize PC-build compatibility expressions.

        CPU models are deliberately recognized by shape rather than a support
        whitelist.  Whether a particular pair is supported belongs to the
        conservative compatibility tool, not to the router.
        """
        cpu_motherboard_pair = (
            (cls.CPU_MODEL_PATTERN.search(query) is not None
             or cls._contains_any(query, cls.CPU_REFERENCE_KEYWORDS))
            and cls._contains_any(query, cls.MOTHERBOARD_KEYWORDS)
            and cls._contains_any(query, cls.TOOL_COMPATIBILITY_KEYWORDS)
        )
        return cpu_motherboard_pair or cls._is_pc_build_compatibility_query(query)

    @classmethod
    def _is_pc_build_compatibility_query(cls, query: str) -> bool:
        if cls._contains_any(query, cls.PC_BUILD_QUERY_KEYWORDS):
            return True
        mentioned_groups = sum(
            cls._contains_any(query, group) for group in cls.PC_BUILD_COMPONENT_GROUPS
        )
        risk_words = cls.TOOL_COMPATIBILITY_KEYWORDS + (
            "能不能装",
            "能装进",
            "会不会挡",
            "够不够",
            "太长",
            "限高",
            "空间",
            "好看",
            "超高",
            "顶内存",
            "前置冷排",
            "顶部冷排",
            "水冷还是风冷",
            "顶部好",
            "前面好",
            "余量",
        )
        return mentioned_groups >= 2 and cls._contains_any(query, risk_words)

    @classmethod
    def _is_tool_spec_query(cls, query: str) -> bool:
        return "b850" in query and cls._contains_any(query, cls.TOOL_SPEC_KEYWORDS)

    @classmethod
    def _is_device_problem(cls, query: str, device_type: str) -> bool:
        """Recognize compositional device + problem-state descriptions."""
        return device_type != "unknown" and cls._contains_any(query, cls.PROBLEM_STATE_KEYWORDS)

    @staticmethod
    def _contains_any(query: str, keywords: tuple[str, ...]) -> bool:
        return any(keyword in query for keyword in keywords)

    @classmethod
    def _match(cls, query: str, keyword_groups: dict[str, tuple[str, ...]]) -> str:
        for category, keywords in keyword_groups.items():
            if cls._contains_any(query, keywords):
                return category
        return "unknown"


supervisor_agent = SupervisorAgent()
