"""AiRadio — AI-likeness detector, returns a Human Voice Index.

The point is not to gate prose, but to keep *our own* reports honest: we write
validation output as a person would, and then we grade our own writing with
the same instrument we would use on a model. If the report scores as
machine-like, the humanizer rewrites it instead of shipping it.

Signals we look for (all cheap, deterministic, explainable):

  * formulaic transitions    — "moreover", "furthermore", "additionally",
                               "in conclusion", "it is worth noting"
  * AI-filler verbs          — "delve", "leverage", "streamline", "foster",
                               "utilize", "robust", "cutting-edge", "seamless"
  * sentence rhythm          — sentences of unnaturally uniform length
  * repeated openers         — too many sentences starting the same way
  * list density             — heavy use of dashes, bullets, and colons
  * hedged inflation         — "very"/"really"/"quite" stacked to sound firm
  * stutter-trigrams         — the same word/word-pair resurfacing on loop

The index is `1 - machine_likeness`, ranging 0 (robotic) to 1 (human).
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

__all__ = ["AiRadio", "rate_human_voice"]

_SENT = re.compile(r"(?<=[.!?])\s+")
_WORDS = re.compile(r"\b[a-zA-Z][a-zA-Z0-9'\-]*\b")
_BULLET = re.compile(r"(^\s*[-*•]|\|\s|,\s*\w+\s*,|: \w)")
_EMDASH = re.compile(r"[—–]| \u2014 ")

_FORMULAIC = {
    "moreover", "furthermore", "additionally", "in conclusion", "in summary",
    "it is important to note", "it is worth noting", "as previously mentioned",
    "in the realm of", "it should be noted that", "lastly",
    "at the end of the day", "to sum up", "all in all",
}
_AI_FILLER = {
    "delve", "leverage", "streamline", "foster", "utilize", "utilise",
    "cutting-edge", "seamless", "robust", "holistic", "synergy", "synergies",
    "game-changer", "revolutionary", "state-of-the-art", "best-in-class",
}
_HEDGE = {"very", "really", "quite", "extremely", "super", "totally", "highly"}


@dataclass
class VoiceScore:
    machine_likeness: float          # 0..1 — closer to 1 is more robotic
    human_index: float               # 1 - machine_likeness
    signals: Dict[str, float]        # raw per-signal counts
    notes: List[str] = None

    def label(self) -> str:
        if self.human_index >= 0.80:
            return "reads human"
        if self.human_index >= 0.60:
            return "mostly human, one tell"
        return "machine-flavored"

    def to_dict(self) -> dict:
        return {
            "machine_likeness": round(self.machine_likeness, 3),
            "human_voice_index": round(self.human_index, 3),
            "label": self.label(),
            "signals": {k: round(v, 4) for k, v in self.signals.items()},
            "notes": self.notes or [],
        }


class AiRadio:
    def score(self, text: str) -> VoiceScore:
        if not text or not text.strip():
            return VoiceScore(1.0, 0.0, {}, ["empty text scores as robotic by default"])

        sents = [s.strip() for s in _SENT.split(text) if s.strip()]
        words = _WORDS.findall(text.lower())
        n_words = len(words)
        base = max(1, n_words)

        formulaic = sum(text.lower().count(f) for f in _FORMULAIC)
        filler = sum(words.count(f) for f in _AI_FILLER)
        hedges = sum(words.count(h) for h in _HEDGE)

        emdash = len(_EMDASH.findall(text))
        bullets = len(_BULLET.findall(text))

        sent_lens = [len(w) for w in sents]
        rhythm = 0.0
        if len(sent_lens) >= 4:
            var = statistics.pstdev(sent_lens) / max(1.0, statistics.mean(sent_lens))
            # extremes in either direction read as written-by-formula
            rhythm = max(0.0, 1.6 * abs(var - 0.35) if var < 0.35 else 0.0)

        openers = [s.split()[0].lower() for s in sents if s.split()]
        repeated = max(0, len(openers) - len(set(openers)))
        opener_rate = repeated / max(1, len(openers))

        # stutter-trigram: a word-pair reappearing inside a short window
        bigrams: Dict[str, int] = {}
        w = words
        for i in range(len(w) - 1):
            key = w[i] + " " + w[i + 1]
            bigrams[key] = bigrams.get(key, 0) + 1
        stutter = sum(1 for c in bigrams.values() if c >= 3) / max(1, len(bigrams))

        signals = {
            "formulaic_transitions": formulaic,
            "ai_filler_verbs": filler,
            "hedged_inflation": hedges,
            "em_dashes": emdash,
            "list_bullets": bullets,
            "sentence_rhythm_anomaly": round(rhythm, 3),
            "repeated_openers": round(opener_rate, 3),
            "stutter_trigrams": round(stutter, 3),
        }

        density = 0.0
        density += min(1.0, formulaic / 4) * 0.30
        density += min(1.0, filler / 6) * 0.25
        density += min(1.0, hedges / 10) * 0.10
        density += min(1.0, (emdash + bullets) / 15) * 0.15
        density += rhythm * 0.10
        density += min(1.0, repeated / 6) * 0.05
        density += min(1.0, stutter / 0.4) * 0.10

        machine = round(min(1.0, density), 3)
        notes = []
        if formulaic:
            notes.append(f"{formulaic} formulaic transition phrase(s)")
        if filler:
            notes.append(f"{filler} AI-filler verb(s) such as 'delve' or 'leverage'")
        if rhythm:
            notes.append("sentence lengths are unnaturally uniform")
        if repeated >= 4:
            notes.append(f"{repeated} sentences share the same opener")
        return VoiceScore(
            machine_likeness=machine,
            human_index=round(1.0 - machine, 3),
            signals=signals,
            notes=notes,
        )


def rate_human_voice(text: str) -> VoiceScore:
    return AiRadio().score(text)