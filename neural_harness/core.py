"""Core harness engine.

A Harness runs a set of Suites, each made of Checks. Every check returns a
CheckResult with a pass/fail verdict, a 0..1 confidence metric, an evidence
list (so numbers can be traced), and a human-readable note.

Design points:

  * Evidence-first. Every score must carry `evidence`: the raw observations
    behind the number, so a claim like "recall accuracy is sound" can be
    reopened and audited tomorrow.
  * Fair failure. A check that raises reports `error` rather than crashing
    the whole run, and the humanized report calls it out honestly.
  * Traceable. Results carry a `trace` of the intermediate values, so the
    human narrative has concrete details to talk about instead of fluff.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Optional


class HumanReadableError(Exception):
    """A problem with the harness setup that a human should read and fix."""


class Phase(str, Enum):
    INFO_HANDLING = "information_handling"
    NEURAL_SYNTHESIS = "neural_synthesis"
    DATA_INTEGRATION = "data_integration"


@dataclass
class CheckResult:
    """Outcome of a single check."""

    check: str
    passed: bool
    metric: float = 0.0            # 0..1 confidence or accuracy, 1 = perfect
    evidence: list = field(default_factory=list)   # raw observations
    trace: dict = field(default_factory=dict)      # intermediate values
    note: str = ""                 # human-style summary of what happened
    duration_ms: float = 0.0
    status: str = "pass"           # pass | warn | fail | error
    phase: Optional[Phase] = None

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "passed": self.passed,
            "status": self.status,
            "metric": round(self.metric, 4),
            "evidence": self.evidence,
            "trace": self.trace,
            "note": self.note,
            "duration_ms": round(self.duration_ms, 2),
            "phase": self.phase.value if self.phase else None,
        }


@dataclass
class Check:
    """A named measurement wrapped in a callable."""

    name: str
    fn: Callable[..., CheckResult]
    phase: Phase
    description: str = ""

    def run(self, **kwargs) -> CheckResult:
        start = time.time()
        try:
            result = self.fn(**kwargs)
        except Exception as exc:  # a broken check must never sink the run
            result = CheckResult(
                check=self.name,
                passed=False,
                status="error",
                note=f"the check itself failed to run ({exc!r})",
            )
        result.duration_ms = round((time.time() - start) * 1000, 2)
        if not result.check:
            result.check = self.name
        result.phase = self.phase
        return result


class Suite:
    """A group of checks in one phase."""

    def __init__(self, phase: Phase, title: str):
        self.phase = phase
        self.title = title
        self.checks: list[Check] = []

    def add(self, name: str, fn: Callable[..., CheckResult], description: str = "") -> "Suite":
        self.checks.append(Check(name, fn, self.phase, description))
        return self

    def run(self, **kwargs) -> list[CheckResult]:
        out = []
        for check in self.checks:
            kwargs["_check_name"] = check.name
            kwargs["_description"] = check.description
            out.append(check.run(**kwargs))
        return out


class Harness:
    """Runs suites, remembers a history of runs, and reports honestly."""

    def __init__(self, project: str, version: str = ""):
        self.project = project
        self.version = version
        self.suites: list[Suite] = []
        self.last_results: list[CheckResult] = []

    def suite(self, phase: Phase, title: str) -> Suite:
        s = Suite(phase, title)
        self.suites.append(s)
        return s

    def run(self, context: Optional[dict] = None) -> list[CheckResult]:
        context = context or {}
        results: list[CheckResult] = []
        for s in self.suites:
            results.extend(s.run(**context))
        self.last_results = results
        return results

    def summary(self) -> dict:
        total = len(self.last_results)
        passed = sum(1 for r in self.last_results if r.status == "pass")
        warned = sum(1 for r in self.last_results if r.status == "warn")
        failed = sum(1 for r in self.last_results if r.status in ("fail", "error"))
        acc = [r for r in self.last_results if r.phase == Phase.DATA_INTEGRATION]
        overall = sum(r.metric for r in self.last_results) / total if total else 1.0
        return {
            "project": self.project,
            "version": self.version,
            "total_checks": total,
            "passed": passed,
            "warned": warned,
            "failed": failed,
            "overall_accuracy": round(overall, 4),
            "integration_accuracy": round(sum(r.metric for r in acc) / len(acc), 4) if acc else None,
            "by_phase": {
                p.value: {
                    "passed": sum(1 for r in self.last_results if r.phase == p and r.status == "pass"),
                    "failed": sum(1 for r in self.last_results if r.phase == p and r.status in ("fail", "error")),
                    "mean_metric": round(
                        sum(r.metric for r in self.last_results if r.phase == p) /
                        max(1, sum(1 for r in self.last_results if r.phase == p)), 4),
                }
                for p in Phase
            },
        }

    def save_history(self, path: str = "harness_history.jsonl") -> None:
        with open(path, "a") as f:
            f.write(json.dumps({
                "ts": time.time(),
                "project": self.project,
                "version": self.version,
                "results": [r.to_dict() for r in self.last_results],
            }) + "\n")

    def as_dict(self) -> dict:
        return {
            "project": self.project,
            "version": self.version,
            "summary": self.summary(),
            "results": [r.to_dict() for r in self.last_results],
        }