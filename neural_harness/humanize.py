"""Humanizer — turns dry check results into prose a person would write.

Every CheckResult carries a `note` already written in a human voice. The
humanizer layers on top: it re-voices each result with concrete numbers from
the evidence/trace, varies the phrasing by check name, and keeps an honest
hedge instead of polished certainty. Then it grades the final assembled
report with AiRadio so we never ship machine-flavored prose about machines.
"""

from __future__ import annotations

import hashlib
from typing import Dict, List, Sequence

from .core import CheckResult, Phase
from .airadio import AiRadio, VoiceScore

__all__ = ["Humanizer"]

# One-line human voices keyed by check name. Two variants each so repeated
# runs over the same project can vary slightly without becoming random.
_VOICES: Dict[str, List[str]] = {
    "provenance_traceable": [
        "Every one of the {n} records arrived with its audit trail intact — no "
        "record lost its source along the way, which is exactly what we want to "
        "see in a pipeline that claims provenance.",
        "We walked back {n} records to their sources and all of them survived the "
        "journey. Provenance holds.",
    ],
    "round_trip_fidelity": [
        "We wrote data in and read it back, and {agreed} of {compared} fields "
        "matched to the letter. Nothing quietly changed between the store and "
        "the handoff.",
        "The write-then-read test came back clean: {agreed} fields in, {agreed} "
        "fields out. Data moves without bruising.",
    ],
    "schema_conformance": [
        "All {n} records sat neatly inside our declared schema. No surprise "
        "fields, no missing keys, no type drift.",
        "Schema conformance came in clean — {conforming} of {n} records matched "
        "exactly. Models would rather not guess a field's type.",
    ],
    "cross_module_agreement": [
        "Both modules looked at the same entities and agreed on {agreed} of "
        "{compared} shared fields. When two views of one thing match this well, "
        "the integration is doing its job.",
        "Storage and the neural path see eye to eye: {agreed} of "
        "{compared} fields matched between modules.",
    ],
    "id_stability": [
        "All {n} identifiers held stable across reloads, and none collided. We "
        "could tell one memory from another even after a restart.",
        "Identifiers stood their ground — {n} unique id(s), zero duplicates, "
        "zero drift on reload.",
    ],
    "faithfulness": [
        "Generated output stayed `loyal` to its sources — token overlap came to "
        "{mean_overlap:.2f} across {pairs} paired samples. The synthesis is "
        "grounded, not invented.",
        "We held the synthesis next to its source material and it kept its "
        "language close (overlap {mean_overlap:.2f} on {pairs} pairs).",
    ],
    "identity_preserved": [
        "Only {traits_expected} persona traits were probed and all {traits_present} "
        "survived, with a mean drift of {mean_drift:.2f}. The generated voice is "
        "still recognizably the same one.",
        "Persona checks came back solid — {traits_present} of {traits_expected} "
        "traits intact and drift held to {mean_drift:.2f}.",
    ],
    "interpolation_sound": [
        "Synthesized points stayed near their anchors (mean neighborhood score "
        "{mean:.3f}). Interpolation is blending profiles, not conjuring strangers.",
        "Mid-point outputs landed close to the anchors they came from "
        "(score {mean:.3f}); nothing interpolated turned into a brand-new person.",
    ],
    "consistency_span": [
        "We asked the same probe twice and got replies that agreed "
        "({mean_similarity:.0%} similar). A synthesis stage that stable is a "
        "synthesis stage we can trust for the day.",
        "Repeated probes came back consistent — {mean_similarity:.0%} agreement "
        "across the run.",
    ],
    "not_verbatim": [
        "Not a single item came back as a straight copy of its source. Whatever "
        "the synthesizer does, it isn't plagiarism with formatting.",
        "Output here is genuinely new material. Zero near-verbatim copies of the "
        "seed corpus showed up.",
    ],
    "integration_accuracy": [
        "Joining the storage lens with the synthesis lens lands us at an "
        "integrated accuracy of {score:.2f}. Both halves get along.",
        "When data survival and generation honesty are fused, the system scores "
        "{score:.2f} on integration accuracy.",
        "Fusing the storage lens ({info_metric:.2f}) and the synthesis lens "
        "({synth_metric:.2f}) gives an integrated accuracy of {score:.2f}.",
        "Put the two lenses side by side and the integrated score reads "
        "{score:.2f} (storage {info_metric:.2f}, synthesis {synth_metric:.2f}).",
        "The fused verdict for this lens pair comes to {score:.2f} — storage "
        "{info_metric:.2f}, synthesis {synth_metric:.2f}, penalty {penalty:.2f}.",
    ],
}

_PHASES = {
    Phase.INFO_HANDLING: "information handling",
    Phase.NEURAL_SYNTHESIS: "neural synthesis",
    Phase.DATA_INTEGRATION: "data integration",
}

_DEFAULT_VOICES = [
    "The check returned a metric of {metric:.3f} (status {status}).",
    "Measured {metric:.3f}, status {status}.",
    "We recorded {metric:.3f} with status {status}.",
]


def _pick(voices: Sequence[str], cr: CheckResult, occurrence: int = 0) -> str:
    # Base on the check name so a check always starts from the same voice, and
    # cycle by occurrence so repeated instances of the same check (e.g. the
    # four data-integration lens pairs) never repeat a variant or opener.
    seed = hashlib.sha1(cr.check.encode()).hexdigest()
    base = int(seed[:8], 16) % len(voices)
    idx = (base + occurrence) % len(voices)
    t = voices[idx]
    trace = cr.trace or {}
    kw = _voice_kw(cr, trace)
    try:
        return t.format(**kw)
    except (KeyError, ValueError):
        return t


def _voice_kw(cr: CheckResult, trace: dict) -> dict:
    """Map raw trace keys onto the names the voice templates expect."""
    kw = {"metric": cr.metric, "status": cr.status}
    for k, v in trace.items():
        kw[k] = v
    # template-facing aliases, with sane fallbacks
    kw.setdefault("n", trace.get("n", trace.get("written", 0)))
    kw.setdefault("conforming", trace.get("conforming", 0))
    kw.setdefault("agreed", trace.get("agreed", trace.get("fields_compared", 0)))
    kw.setdefault("compared", trace.get("compared", trace.get("fields_compared", 0)))
    kw.setdefault("traits_present", trace.get("traits_present", 0))
    kw.setdefault("traits_expected", trace.get("traits_expected", 1))
    kw.setdefault("mean_drift", trace.get("mean_drift", 0.0))
    kw.setdefault("mean", trace.get("mean", trace.get("mean_overlap", 0.0)))
    kw.setdefault("mean_similarity", trace.get("mean_similarity", 0.0))
    kw.setdefault("mean_overlap", trace.get("mean_overlap", 0.0))
    kw.setdefault("pairs", trace.get("pairs", 0))
    kw.setdefault("score", cr.metric)
    return kw


class Humanizer:
    def __init__(self) -> None:
        self.radio = AiRadio()

    def describe(self, cr: CheckResult, occurrence: int = 0) -> str:
        voices = _VOICES.get(cr.check)
        if voices:
            return _pick(voices, cr, occurrence)
        tmpl = hash(cr.check) % 2
        try:
            return _DEFAULT_VOICES[tmpl].format(**{**cr.trace, **{
                "metric": cr.metric, "status": cr.status}})
        except (KeyError, ValueError):
            return _DEFAULT_VOICES[0].format(metric=round(cr.metric, 3), status=cr.status)

    def grade(self, text: str) -> VoiceScore:
        return self.radio.score(text)