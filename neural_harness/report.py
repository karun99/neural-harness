"""Report builder — one narrative, machine-readable underneath.

`build_report` returns both:
  * `prose`   - human-sounding narrative paragraphs, graded by AiRadio
  * `results` - the structured summary a CI job or tomorrow's evaluator reads

The prose is assembled from the Humanizer's per-result voices plus a wrapper
paragraph. We then score the assembled prose and, if it dips below a voice
threshold, append a short honest note instead of silently shipping it.
"""

from __future__ import annotations

from typing import List, Optional

from .core import CheckResult, Harness, Phase
from .humanize import Humanizer

__all__ = ["build_report", "to_markdown"]

_PHASE_LABELS = {
    Phase.INFO_HANDLING: "information handling",
    Phase.NEURAL_SYNTHESIS: "neural synthesis",
    Phase.DATA_INTEGRATION: "data integration",
}


def _phase_paragraph(phase: Phase, results: List[CheckResult], h: Humanizer) -> str:
    if not results:
        return ""
    good = sum(1 for r in results if r.passed)
    n = len(results)
    label = _PHASE_LABELS[phase]
    if good == n:
        opener = f"{label.capitalize()}: {n} checks, all clear."
    else:
        opener = f"{label.capitalize()}: {n} checks, {good} clean."
    body_parts: List[str] = []
    seen: dict = {}
    for r in results:
        occ = seen.get(r.check, 0)
        seen[r.check] = occ + 1
        body_parts.append(h.describe(r, occurrence=occ))
    body = "\n\n".join(body_parts)
    return opener + "\n\n" + body


def build_report(harness: Harness, results: List[CheckResult],
                 fused: Optional[List[CheckResult]] = None) -> dict:
    h = Humanizer()
    all_results = list(results) + list(fused or [])
    summary = harness.summary()

    intro = (
        f"{harness.project} finished its harness run with an overall accuracy of "
        f"{summary['overall_accuracy']:.2f}. {summary['passed']} of "
        f"{summary['total_checks']} checks passed outright, {summary['warned']} "
        f"flagged a warning, and {summary['failed']} failed."
    )
    if summary.get("integration_accuracy") is not None:
        intro += (
            f" Measured on data integration specifically, accuracy came to "
            f"{summary['integration_accuracy']:.2f}."
        )

    bodies: List[str] = []
    for phase in Phase:
        group = [r for r in all_results if r.phase == phase]
        para = _phase_paragraph(phase, group, h)
        if para:
            bodies.append(para)

    prose = intro + "\n\n" + "\n\n".join(bodies)
    voice = h.grade(prose)

    report = {
        "project": harness.project,
        "version": harness.version,
        "summary": summary,
        "prose": prose,
        "voice": voice.to_dict(),
        "results": [r.to_dict() for r in all_results],
    }
    if voice.human_index < 0.60:
        report["voice_note"] = (
            "The assembled prose scored below our human-voice threshold; "
            "the raw structured results above are the authoritative record."
        )
    return report


def to_markdown(report: dict) -> str:
    """Render a human-readable markdown document for presentation/JOSS."""
    s = report["summary"]
    v = report["voice"]
    lines = [
        f"# {report['project']} - validation report",
        "",
        report["prose"],
        "",
        "## Summary",
        "",
        f"- overall accuracy: **{s['overall_accuracy']:.3f}**",
        f"- integration accuracy: **{s.get('integration_accuracy')}**",
        f"- passed: **{s['passed']}** / {s['total_checks']}",
        f"- warnings: {s['warned']}, failures: {s['failed']}",
        f"- human voice index: **{v['human_voice_index']:.3f}** ({v['label']})",
        "",
        "## Checks",
        "",
        "| check | phase | status | metric | duration ms |",
        "|---|---|---|---|---|",
    ]
    for r in report["results"]:
        phase_label = _PHASE_LABELS.get(r.get("phase"), "")
        lines.append(
            f"| `{r['check']}` | {phase_label} | {r['status']} | "
            f"{r['metric']:.3f} | {r['duration_ms']} |"
        )
    lines.append("")
    return "\n".join(lines)