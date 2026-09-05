"""Adaptive and explainable troubleshooting for hardware support."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2


@dataclass(frozen=True)
class Check:
    check_id: str
    action: str
    question: str
    instructions: str
    abnormal_likelihood: dict[str, float]
    risk_level: str = "low"


@dataclass(frozen=True)
class DiagnosticProfile:
    hypotheses: dict[str, tuple[str, float]]
    checks: tuple[Check, ...]


class AdaptiveDiagnosisService:
    """Update fault probabilities and choose the check with most information gain."""

    SAFETY_TERMS = (
        "冒烟", "烧焦", "焦味", "火花", "漏液", "触电", "起火",
        "smoke", "burning smell", "spark", "electric shock", "liquid leak",
    )

    PROFILES = {
        "no_display": DiagnosticProfile(
            hypotheses={
                "power_delivery": ("主板或 CPU 供电连接异常", 0.22),
                "memory_training": ("内存安装或训练失败", 0.31),
                "gpu_output_path": ("显卡、线缆或显示输入链路异常", 0.29),
                "firmware_config": ("BIOS 配置或初始化状态异常", 0.18),
            },
            checks=(
                Check(
                    "debug_led", "读取主板诊断灯", "CPU、DRAM、VGA、BOOT 哪个灯常亮？",
                    "保持设备断电后确认接线；通电观察时不要触碰主板元件。记录常亮灯，若均熄灭选择“正常”。",
                    {"power_delivery": .45, "memory_training": .82, "gpu_output_path": .76, "firmware_config": .28},
                ),
                Check(
                    "memory_reseat", "单条内存重新安装", "使用一条内存按说明书推荐插槽安装后，画面是否恢复？",
                    "关机、拔掉电源并释放余电，再重新安装单条内存。恢复显示选择“正常”，仍无显示选择“异常”。",
                    {"power_delivery": .18, "memory_training": .86, "gpu_output_path": .20, "firmware_config": .32},
                ),
                Check(
                    "display_path", "核对显示输出链路", "切换正确输入源并更换线缆或输出口后，画面是否恢复？",
                    "先确认显示器输入源，再测试另一根线缆和显卡的其他输出口；不要热插拔内部供电线。",
                    {"power_delivery": .12, "memory_training": .15, "gpu_output_path": .88, "firmware_config": .24},
                ),
                Check(
                    "cpu_power", "核对主板与 CPU 供电", "24-pin 与 CPU 8-pin 重新插紧后能否完成自检？",
                    "关机并拔掉电源后操作。确认 CPU 供电线没有误用显卡供电线；不确定接口时停止并转人工。",
                    {"power_delivery": .91, "memory_training": .16, "gpu_output_path": .12, "firmware_config": .18},
                    "medium",
                ),
                Check(
                    "clear_cmos", "恢复 BIOS 默认配置", "按主板说明书清除 CMOS 后，能否正常显示？",
                    "必须断电并严格按对应型号说明书操作。无法确认跳线位置时不要尝试。",
                    {"power_delivery": .10, "memory_training": .35, "gpu_output_path": .20, "firmware_config": .86},
                    "medium",
                ),
            ),
        ),
        "boot_failure": DiagnosticProfile(
            hypotheses={
                "power_delivery": ("电源、主供电或 CPU 供电异常", .38),
                "front_panel": ("机箱开关或前面板接线异常", .22),
                "short_circuit": ("装机短路或保护触发", .18),
                "component_post": ("核心部件导致 POST 失败", .22),
            },
            checks=(
                Check(
                    "standby_power", "检查待机供电迹象", "主板待机灯或网口灯是否亮？",
                    "只观察灯光，不拆开电源。没有任何待机迹象选择“异常”。",
                    {"power_delivery": .88, "front_panel": .25, "short_circuit": .52, "component_post": .12},
                ),
                Check(
                    "front_panel", "核对开机针脚", "按说明书核对 PWR_SW 接线后能否开机？",
                    "断电后按主板说明书核对前面板针脚；不要用不确定的金属工具短接。",
                    {"power_delivery": .18, "front_panel": .92, "short_circuit": .18, "component_post": .10},
                    "medium",
                ),
                Check(
                    "minimal_boot", "使用最小硬件配置", "只保留 CPU、散热、单条内存后能否启动？",
                    "断电并释放余电后移除非必要设备。若不熟悉拆装，选择“不确定”并转人工。",
                    {"power_delivery": .30, "front_panel": .12, "short_circuit": .78, "component_post": .72},
                    "medium",
                ),
            ),
        ),
        "overheating": DiagnosticProfile(
            hypotheses={
                "cooler_contact": ("散热器接触或硅脂状态异常", .36),
                "fan_pump": ("风扇或水泵未工作", .31),
                "airflow": ("机箱风道或积灰问题", .21),
                "workload_config": ("负载、电压或风扇曲线配置异常", .12),
            },
            checks=(
                Check(
                    "idle_temperature", "记录待机温度", "进入系统静置十分钟后温度是否仍明显偏高？",
                    "记录环境温度、CPU/GPU 温度和占用率；温度快速逼近保护阈值时立即关机。",
                    {"cooler_contact": .86, "fan_pump": .82, "airflow": .48, "workload_config": .35},
                ),
                Check(
                    "fan_pump_speed", "查看风扇与水泵转速", "BIOS 中对应转速是否为 0 或明显异常？",
                    "只在 BIOS 界面读取转速，不触摸正在旋转的风扇。异常或为 0 选择“异常”。",
                    {"cooler_contact": .20, "fan_pump": .94, "airflow": .18, "workload_config": .25},
                ),
                Check(
                    "panel_test", "进行侧板对比测试", "打开侧板后，同负载温度是否明显下降？",
                    "短时对比并避免异物进入机箱。明显下降选择“异常”，代表原风道可能有问题。",
                    {"cooler_contact": .18, "fan_pump": .22, "airflow": .86, "workload_config": .24},
                ),
            ),
        ),
    }

    OUTCOME_ALIASES = {
        "pass": "normal", "fail": "abnormal",
        "正常": "normal", "异常": "abnormal", "不确定": "unknown",
    }

    def next_check(self, query: str, fault_type: str, observations: list[dict[str, str]]) -> dict:
        if self._has_safety_risk(query):
            return self._safety_stop()

        profile_name = fault_type if fault_type in self.PROFILES else self._infer_profile(query)
        profile = self.PROFILES[profile_name]
        valid_check_ids = {check.check_id for check in profile.checks}
        normalized = {
            item["check_id"]: self.OUTCOME_ALIASES.get(
                item["outcome"].casefold(), item["outcome"].casefold()
            )
            for item in observations
            if item.get("check_id") in valid_check_ids
        }
        posterior = self._posterior(profile, normalized)
        remaining = [check for check in profile.checks if check.check_id not in normalized]
        ranked = self._ranked_hypotheses(profile, posterior)

        if not remaining:
            return {
                "status": "complete",
                "profile": profile_name,
                "next_check": None,
                "hypotheses": ranked,
                "confidence": ranked[0]["probability"],
                "should_handoff": ranked[0]["probability"] < .70,
                "stop_reason": "all_checks_completed",
                "explanation": "可用检查已完成；结果和检查记录可随工单转交人工客服。",
            }

        scored = [(self._information_gain(check, posterior), check) for check in remaining]
        information_gain, selected = max(
            scored, key=lambda item: (item[0], -profile.checks.index(item[1]))
        )
        return {
            "status": "in_progress",
            "profile": profile_name,
            "next_check": {
                "check_id": selected.check_id,
                "action": selected.action,
                "question": selected.question,
                "instructions": selected.instructions,
                "risk_level": selected.risk_level,
                "information_gain": round(information_gain, 4),
            },
            "hypotheses": ranked,
            "confidence": ranked[0]["probability"],
            "should_handoff": False,
            "stop_reason": "",
            "explanation": f"选择“{selected.action}”，因为它在剩余检查中最能区分当前故障原因。",
        }

    def _posterior(
        self, profile: DiagnosticProfile, observations: dict[str, str]
    ) -> dict[str, float]:
        weights = {key: prior for key, (_, prior) in profile.hypotheses.items()}
        checks = {check.check_id: check for check in profile.checks}
        for check_id, outcome in observations.items():
            if outcome == "unknown":
                continue
            check = checks[check_id]
            for hypothesis in weights:
                likelihood = check.abnormal_likelihood[hypothesis]
                weights[hypothesis] *= likelihood if outcome == "abnormal" else 1 - likelihood
        total = sum(weights.values())
        if total == 0:
            return {key: 1 / len(weights) for key in weights}
        return {key: value / total for key, value in weights.items()}

    def _information_gain(self, check: Check, posterior: dict[str, float]) -> float:
        current_entropy = self._entropy(posterior.values())
        abnormal_probability = sum(
            posterior[h] * check.abnormal_likelihood[h] for h in posterior
        )
        expected_entropy = 0.0
        for is_abnormal, outcome_probability in (
            (True, abnormal_probability),
            (False, 1 - abnormal_probability),
        ):
            if outcome_probability <= 0:
                continue
            outcome_posterior = {
                h: posterior[h]
                * (
                    check.abnormal_likelihood[h]
                    if is_abnormal
                    else 1 - check.abnormal_likelihood[h]
                )
                / outcome_probability
                for h in posterior
            }
            expected_entropy += outcome_probability * self._entropy(
                outcome_posterior.values()
            )
        return current_entropy - expected_entropy

    @staticmethod
    def _entropy(probabilities) -> float:
        return -sum(value * log2(value) for value in probabilities if value > 0)

    @staticmethod
    def _ranked_hypotheses(
        profile: DiagnosticProfile, posterior: dict[str, float]
    ) -> list[dict]:
        return [
            {
                "code": code,
                "label": profile.hypotheses[code][0],
                "probability": round(probability, 4),
            }
            for code, probability in sorted(
                posterior.items(), key=lambda item: item[1], reverse=True
            )
        ]

    @classmethod
    def _has_safety_risk(cls, query: str) -> bool:
        normalized = query.casefold()
        return any(term in normalized for term in cls.SAFETY_TERMS)

    @staticmethod
    def _infer_profile(query: str) -> str:
        normalized = query.casefold()
        if any(term in normalized for term in ("过热", "高温", "温度", "overheat")):
            return "overheating"
        if any(term in normalized for term in ("无法开机", "不通电", "无法启动", "boot")):
            return "boot_failure"
        return "no_display"

    @staticmethod
    def _safety_stop() -> dict:
        return {
            "status": "safety_stop",
            "profile": "safety",
            "next_check": {
                "check_id": "disconnect_power",
                "action": "立即断电并停止自行排查",
                "question": "设备是否已经断电并远离可燃物？",
                "instructions": "关闭电源；在安全情况下拔掉插头。不要再次通电、拆开电源或触碰漏液区域，请联系人工客服或专业维修人员。",
                "risk_level": "critical",
                "information_gain": 0.0,
            },
            "hypotheses": [],
            "confidence": 1.0,
            "should_handoff": True,
            "stop_reason": "electrical_or_fire_hazard",
            "explanation": "检测到可能涉及电气、起火或漏液风险，安全规则优先于继续诊断。",
        }


adaptive_diagnosis_service = AdaptiveDiagnosisService()
