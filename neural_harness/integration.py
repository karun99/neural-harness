"""Data integration — the fused accuracy claim, made measurable.

Information handling tells us data survives the journey. Neural synthesis
tells us generated output is honest. But neither alone proves the *integrated*
system works, because the two lenses can disagree: data can round-trip
perfectly while synthesis hallucinates on top of it, or synthesis can be
faithful only because it copies the source verbatim (which `not_verbatim`
flags).

This module fuses both suites into a single integration-accuracy verdict:

    integration_accuracy = w1 * info_accuracy + w2 * synth_accuracy
                           - consistency_penalty

where the penalty grows when the lenses contradict one another. It is the
number a reviewer can quote, and it carries the full per-suite detail so the
number can be opened up again.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .core import CheckResult, Phase, Suite, Harness, Check
from .infohand import information_handling_suite
from .synth import neural_synthesis_suite

__all__ = ["integration_accuracy", "data_integration_suite", "fused_report"]


def integration_accuracy(
    info: CheckResult,
    synth: CheckResult,
    info_weight: float = 0.5,
    synth_weight: float = 0.5,
    consistency_threshold: float = 0.45,
) -> CheckResult:
    """Fuse one info-handling verdict and one synthesis verdict.

    The penalty is large when the two lenses strongly disagree: e.g. storage
    fidelity perfect but synthesis faithfulness near zero, or synthesis
    "faithful" only because it copies verbatim. The `phase` of both inputs is
    expected to matter — callers pass the fused pair; the returned result is
    tagged for the DATA_INTEGRATION phase.
    """
    iw = max(0.0, info.metric)
    sw = max(0.0, synth.metric)
    raw = info_weight * iw + synth_weight * sw

    # consistency penalty: how far apart are the two lenses?
    gap = abs(iw - sw)
    verbatim_penalty = 0.0
    if synth.check == "not_verbatim" and not synth.passed:
        verbatim_penalty = min(0.35, (1.0 - synth.metric) * 0.5)
    if info.check == "round_trip_fidelity" and not info.passed:
        verbatim_penalty += 0.0  # already captured by gap

    penalty = 0.0
    if gap > consistency_threshold:
        penalty = min(0.40, (gap - consistency_threshold) * 0.8)
    penalty = round(min(1.0, penalty + verbatim_penalty), 4)

    score = round(max(0.0, min(1.0, raw - penalty)), 4)
    passed = score >= 0.7
    note = (
        f"When we join the storage lens ({info.metric:.2f}) with the synthesis "
        f"lens ({synth.metric:.2f}), the integrated accuracy lands at {score:.2f}. "
        f"That is a system the two halves can agree on."
        if passed else
        f"Storage gives {info.metric:.2f} but synthesis only {synth.metric:.2f}, "
        f"and the lenses are {gap:.2f} apart — so the integrated system rates "
        f"{score:.2f}. Data may survive the journey but the neural layer is "
        f"re-writing it."
    )
    return CheckResult(
        check="integration_accuracy",
        passed=passed,
        metric=score,
        phase=Phase.DATA_INTEGRATION,
        evidence=[
            {"lens": info.check, "metric": info.metric, "passed": info.passed},
            {"lens": synth.check, "metric": synth.metric, "passed": synth.passed},
            {"consistency_gap": round(gap, 4), "penalty": penalty},
        ],
        trace={
            "info_weight": info_weight,
            "synth_weight": synth_weight,
            "raw": round(raw, 4),
            "penalty": penalty,
            "info_metric": info.metric,
            "synth_metric": synth.metric,
        },
        note=note,
    )


def data_integration_suite() -> Suite:
    """Suites are wired inside `fused_report`, since integrations need results."""
    return Suite(Phase.DATA_INTEGRATION, "Data integration")


def _pick(results: List[CheckResult], names: list) -> Optional[CheckResult]:
    wanted = set(names)
    for r in results:
        if r.check in wanted:
            return r
    return None


def fused_report(harness: Harness, results: List[CheckResult],
                 pairs: Optional[List[tuple]] = None,
                 info_names: Optional[List[str]] = None,
                 synth_names: Optional[List[str]] = None) -> List[CheckResult]:
    """Generate the data-integration lens: fuse default lens pairs.

    Each fused result is appended to `results` and returned separately so the
    report builder can cite them as the integration phase.
    """
    default_pairs = [
        ("round_trip_fidelity", "faithfulness"),
        ("schema_conformance", "not_verbatim"),
        ("provenance_traceable", "identity_preserved"),
        ("cross_module_agreement", "consistency_span"),
    ]
    info_names = info_names or ["round_trip_fidelity", "schema_conformance",
                                "provenance_traceable"]
    synth_names = synth_names or ["faithfulness", "not_verbatim",
                                  "interpolation_sound"]
    pairs = pairs or default_pairs

    fused: List[CheckResult] = []
    for i, s in pairs:
        ri = _pick(results, [i])
        rs = _pick(results, [s])
        if ri is None or rs is None:
            continue
        fused.append(integration_accuracy(ri, rs))
    return fused