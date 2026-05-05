"""Metric package marker.

Behavioral metric engines are implemented after the social-navigation metric
spec is frozen. Unit 7 intentionally exposes no scoring functions yet; report
code must refuse calibrated score mode unless a caller explicitly confirms the
metric freeze.
"""

METRIC_SPEC_PATH = "docs/specs/social-navigation-metrics.md"

__all__ = ["METRIC_SPEC_PATH"]
