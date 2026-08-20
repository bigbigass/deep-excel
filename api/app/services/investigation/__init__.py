"""确定性与证据约束的质量调查服务。"""

from api.app.services.investigation.ai_pipeline import (
    apply_ai_result_to_case,
    run_evidence_grounded_ai,
)
from api.app.services.investigation.baseline import run_baseline_investigation
from api.app.services.investigation.change_points import detect_mean_change_point
from api.app.services.investigation.factor_ranking import rank_failure_associations
from api.app.services.investigation.group_comparison import compare_group_failure_rates
from api.app.services.investigation.profiling import profile_dataset
from api.app.services.investigation.spc_signals import detect_spc_signals
from api.app.services.investigation.tool_registry import (
    InvestigationToolRegistry,
    build_default_tool_registry,
)

__all__ = [
    "InvestigationToolRegistry",
    "apply_ai_result_to_case",
    "build_default_tool_registry",
    "compare_group_failure_rates",
    "detect_mean_change_point",
    "detect_spc_signals",
    "profile_dataset",
    "rank_failure_associations",
    "run_baseline_investigation",
    "run_evidence_grounded_ai",
]
