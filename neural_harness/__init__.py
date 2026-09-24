"""neural_harness — a validation harness engine for neural projects.

Three lenses over one engine:

  * information handling  — how faithfully a project moves data around
    (provenance, round-trip integrity, schema mapping, cross-module agreement)
  * neural synthesis      — how honestly a project generates new material
    (faithfulness to source, identity preservation, interpolation, drift)
  * data integration      — whether the two lenses agree when fused, so the
    accuracy claim of "data integrated through the pipeline" is actually
    measurable rather than assumed.

Reports are written to read as though a careful human wrote them, and every
report passes through an AI-likeness detector (the Human Voice Index) so we
never ship machine-sounding prose about machines.

Standard library only. Python 3.9+.
"""

from .core import (
    Check, CheckResult, Phase, Suite, Harness, HumanReadableError,
)
from .humanize import Humanizer
from .airadio import AiRadio, rate_human_voice
from .report import build_report

__version__ = "1.0.0"
__all__ = [
    "Check", "CheckResult", "Phase", "Suite", "Harness",
    "HumanReadableError", "Humanizer", "AiRadio", "rate_human_voice",
    "build_report", "__version__",
]