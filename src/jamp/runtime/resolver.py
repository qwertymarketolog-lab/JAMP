CAPABILITY_MAP = {
    "search_and_extraction": ("C01", "C06"),
    "tool_execution_agent": ("C02", "C05"),
    "long_context_analysis": ("C03", "C08"),
    "strict_compliance_safety": ("C04", "C07", "C09"),
}


class CapabilityResolver:
    def get_required_capabilities(self, task_profile: str) -> tuple[str, ...]:
        try:
            return CAPABILITY_MAP[task_profile]
        except KeyError as exc:
            raise ValueError(f"Unknown task profile: {task_profile}") from exc
