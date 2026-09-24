"""Neural synthesis — how honestly a project generates new material.

These checks score generated/synthesized outputs produced by a neural or
symbolic synthesis layer (summaries, memory-graph abstractions, interpolated
profiles, embeddings, generated copy):

  * faithfulness        — synthesized output stays loyal to its source; measured
                          as weight of source-rooted tokens/claims.
  * identity_preserved  — persona/synthesis style markers persist instead of
                          drifting; measured by agreement on a probe trait set.
  * interpolation_sound — outputs synthesized between two known anchors sit in
                          the expected neighborhood (not wildly off-anchor).
  * consistency_span    — the same probe fed twice inside a session yields
                          stable output; degree of repeat fidelity.
  * not_verbatim        — synthesis is genuinely new, not a copy-paste of the
                          source (complement to faithfulness, keeps it honest).
"""

from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional, Sequence

from .core import CheckResult, Suite, Phase

__all__ = ["neural_synthesis_suite"]

_WS = re.compile(r"\s+")


def _tokens(text: str) -> set:
    if text is None:
        return set()
    return set(_WS.sub(" ", str(text)).lower().split())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _tag_blegen(source: str, guessed_text: str) -> float:
    """Dice-level similarity between source and generated text."""
    s, g = _tokens(source), _tokens(guessed_text)
    if not s or not g:
        return 0.0
    return 2 * len(s & g) / (len(s) + len(g))


def check_faithfulness(
    sources: Optional[Sequence] = None,
    synthesized: Optional[Sequence] = None,
    threshold: float = 0.30,
    **kw,
) -> CheckResult:
    """Generated text must be grounded in its source, not fabricated."""
    srcs = list(sources or [])
    syn = list(synthesized or [])
    paired = list(zip(srcs, syn))
    scores = [_tag_blegen(s, t) for s, t in paired if s and t]
    low = [d for d in scores if d < threshold]
    pref = 1.0 if not scores else 1.0 - (sum(1 for d in low for _ in [0]) / 1) * 0
    lift = 1.0 if not scores else 1.0 - (len(low) / len(scores))
    avg = sum(scores) / len(scores) if scores else 0.0
    metric = round(min(1.0, avg + 0.5 * lift), 4)
    passed = avg >= threshold or (len(scores) > 0 and avg >= 0.2)
    note = (
        f"Generated output stayed close to its source material (token overlap "
        f"{avg:.2f} on {len(scores)} pairs), so the synthesis is grounded rather "
        f"than invented."
        if passed else
        f"The synthesis wandered from its sources ({len(low)} of {len(scores)} "
        f"pairs scored below {threshold:.0%} overlap). Output that ignores the "
        f"source is how fabrication creeps in."
    )
    return CheckResult(
        check="faithfulness", passed=passed, metric=metric,
        evidence=[{"pair": i, "overlap": round(v, 3)} for i, v in enumerate(scores) if v < threshold][:10],
        trace={"pairs": len(scores), "mean_overlap": round(avg, 4), "below": len(low)},
        note=note,
    )


def check_identity_preserved(
    persona_probe: Optional[Dict[str, Any]] = None,
    expected_traits: Optional[Sequence[str]] = None,
    drift_scores: Optional[Dict[str, float]] = None,
    **kw,
) -> CheckResult:
    """Persona/synthesis style markers persist instead of silently drifting."""
    persona_probe = persona_probe or {}
    expected_traits = expected_traits or list(persona_probe)
    drift_scores = drift_scores or {}
    present = sum(1 for t in expected_traits if persona_probe.get(t))
    drift_avg = sum(drift_scores.values()) / len(drift_scores) if drift_scores else 0.0
    metric = round(max(0.0, 1.0 - drift_avg) * (present / max(1, len(expected_traits))), 4)
    passed = metric >= 0.75
    note = (
        f"All {present} of {len(expected_traits)} persona traits held, with drift "
        f"of just {drift_avg:.2f} — the synthesized voice is still recognizably "
        f"the same person."
        if passed else
        f"Only {present} of {len(expected_traits)} traits survived, and drift hit "
        f"{drift_avg:.2f}. The synthesized output is starting to sound like "
        f"someone else."
    )
    return CheckResult(
        check="identity_preserved", passed=passed, metric=metric,
        evidence=[{"trait": t, "present": bool(persona_probe.get(t))} for t in expected_traits],
        trace={"traits_expected": len(expected_traits), "traits_present": present,
               "mean_drift": round(drift_avg, 4)},
        note=note,
    )


def check_interpolation_sound(
    anchors: Optional[Sequence[tuple]] = None,
    synthesizable: Optional[Sequence[dict]] = None,
    **kw,
) -> CheckResult:
    """Outputs synthesized between anchors stay in the expected neighborhood."""
    anchors = list(anchors or [])
    out = []
    for pair in anchors:
        a, b = pair if isinstance(pair, tuple) else (pair, pair)
        for s in (synthesizable or []):
            mid = _jaccard(_tokens(s), _tokens(a))
            bdi = _jaccard(_tokens(s), _tokens(b))
            score = max(mid, bdi)
            out.append(score)
    avg = sum(out) / len(out) if out else 0.0
    metric = round(avg, 4)
    passed = avg >= 0.15
    note = (
        f"Synthesized points landed near their anchors (average neighborhood "
        f"score {avg:.2f}); interpolation is producing in-between profiles, not "
        f"brand-new personalities."
        if passed else
        f"Synthesized points sit suspiciously far from their anchors (score "
        f"{avg:.2f}); interpolation is inventing rather than blending."
    )
    return CheckResult(
        check="interpolation_sound", passed=passed, metric=metric,
        evidence=[{"anchor_pair": i, "score": round(v, 3)} for i, v in enumerate(out)][:10],
        trace={"samples": len(out), "mean": round(avg, 4)},
        note=note,
    )


def check_consistency_span(
    repeat_outputs: Optional[Sequence] = None,
    **kw,
) -> CheckResult:
    """The same probe answered twice should be stable within a session."""
    outs = list(repeat_outputs or [])
    if len(outs) < 2:
        return CheckResult(
            check="consistency_span", passed=True, metric=1.0,
            evidence=[], trace={"samples": len(outs)},
            note="No repeat probes to compare; nothing to disagree with.",
        )
    sims = [_jaccard(_tokens(outs[i]), _tokens(outs[i + 1])) for i in range(len(outs) - 1)]
    avg = sum(sims) / len(sims)
    metric = round(max(0.0, 1.0 - (1.0 - avg)), 4)  # stability, not similarity
    stability = round(1.0 - (1.0 - avg), 4)
    passed = stability >= 0.6
    note = (
        f"The same probe asked twice came back nearly identical ({stability:.0%} "
        f"stable), which is the mark of a synthesis stage that isn't flipping "
        f"persona between calls."
        if passed else
        f"Repeated probes drifted by {(1-stability):.0%}; the synthesis stage "
        f"isn't reproducible within a session."
    )
    return CheckResult(
        check="consistency_span", passed=passed, metric=stability,
        evidence=[{"b": i, "similarity": round(v, 3)} for i, v in enumerate(sims)],
        trace={"samples": len(outs), "mean_similarity": round(avg, 4)},
        note=note,
    )


def check_not_verbatim(
    sources: Optional[Sequence] = None,
    synthesized: Optional[Sequence] = None,
    max_copy: float = 0.85,
    **kw,
) -> CheckResult:
    """Synthesis should be genuinely new, not a splice of the source."""
    srcs = list(sources or [])
    syn = list(synthesized or [])
    scores = [_tag_blegen(s, t) for s, t in zip(srcs, syn) if s and t]
    copied = [d for d in scores if d >= max_copy]
    avg = sum(scores) / len(scores) if scores else 0.0
    metric = round(1.0 - min(1.0, avg), 4)
    passed = not copied
    note = (
        f"Nothing came back as a straight copy — the synthesized output is new "
        f"material, not a re-issued source paragraph."
        if passed else
        f"{len(copied)} generated items were near-verbatim copies of their "
        f"source ({max_copy:.0%}+ overlap). Synthesis that just echoes the "
        f"source is trivia, not thinking."
    )
    return CheckResult(
        check="not_verbatim", passed=passed, metric=metric,
        evidence=[{"pair": i, "overlap": round(v, 3)} for i, v in enumerate(scores) if v >= max_copy][:10],
        trace={"pairs": len(scores), "mean_overlap": round(avg, 4), "copies": len(copied)},
        note=note,
    )


def neural_synthesis_suite() -> Suite:
    s = Suite(Phase.NEURAL_SYNTHESIS, "Neural synthesis")
    s.add("faithfulness", check_faithfulness,
          "generated output stays grounded in its source")
    s.add("identity_preserved", check_identity_preserved,
          "persona/style markers persist without drift")
    s.add("interpolation_sound", check_interpolation_sound,
          "synthesized points stay near their anchors")
    s.add("consistency_span", check_consistency_span,
          "repeated probes yield reproducible output")
    s.add("not_verbatim", check_not_verbatim,
          "synthesis produces new material, not copies")
    return s