"""Composed Phase 1.5 corpus-readiness repository."""
from .readiness_base import ReadinessBase
from .readiness_gate import ReadinessGateMixin
from .readiness_models import GateFinding, GateReport, GateThresholds
from .readiness_reports import ReadinessReportingMixin
from .readiness_sampling import ReadinessSamplingMixin


class ReadinessRepository(
    ReadinessSamplingMixin, ReadinessReportingMixin, ReadinessGateMixin, ReadinessBase
):
    """Internal, evidence-pinned readiness workflow."""

    pass


__all__ = [
    "GateFinding", "GateReport", "GateThresholds", "ReadinessRepository"
]
