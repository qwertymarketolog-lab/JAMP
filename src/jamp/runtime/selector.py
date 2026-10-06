POOL_EXPECTATIONS = {
    "search_and_extraction": 12,
    "tool_execution_agent": 7,
    "long_context_analysis": 0,
    "strict_compliance_safety": 2,
}


class ModelSelector:
    def select(self, eligible_models, task_profile):
        pool = tuple(eligible_models)
        expected = POOL_EXPECTATIONS[task_profile]
        if len(pool) != expected:
            raise ValueError(
                f"Qualified pool cardinality mismatch: expected {expected}, got {len(pool)}"
            )
        if not pool:
            return "REFUSE", "ZERO_ELIGIBLE_MODELS"
        return (
            "EXECUTE",
            pool if task_profile == "strict_compliance_safety" else pool[0],
        )

    def select_model(self, eligible_models, task_profile):
        return self.select(eligible_models, task_profile)
