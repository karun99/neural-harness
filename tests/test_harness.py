"""Tests for the harness engine, its three lenses, and the demo/site CLI."""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from neural_harness import Harness, CheckResult, Phase, HumanReadableError
from neural_harness.infohand import (
    check_provenance, check_round_trip, check_schema,
    check_cross_module, check_id_stability,
)
from neural_harness.synth import (
    check_faithfulness, check_identity_preserved,
    check_interpolation_sound, check_consistency_span, check_not_verbatim,
)
from neural_harness.integration import integration_accuracy, fused_report
from neural_harness.humanize import Humanizer
from neural_harness.airadio import AiRadio
from neural_harness.projects import run_project, ALL


def ok(fn, **kw) -> CheckResult:
    return fn(**kw)


def test_provenance_clean():
    r = check_provenance([{"id": 1, "source_id": "a"}, {"id": 2, "source_id": "b"}])
    assert r.passed and r.metric == 1.0


def test_provenance_broken_chain():
    r = check_provenance([{"id": 1}, {"id": 2, "source_id": "b"}])
    assert not r.passed and r.metric == 0.5


def test_round_trip_fidelity():
    wrote = [{"id": i, "content": f"value-{i}"} for i in range(50)]
    r = check_round_trip(records=wrote, read_back=[dict(x) for x in wrote])
    assert r.passed and r.metric == 1.0


def test_round_trip_detects_drift():
    wrote = [{"id": i, "content": f"value-{i}"} for i in range(50)]
    read = [dict(x) for x in wrote]
    read[3]["content"] = "mutated"
    r = check_round_trip(records=wrote, read_back=read)
    assert not r.passed


def test_schema_conformance_clean_and_broken():
    s = {"id": int, "content": str}
    assert check_schema([{"id": 1, "content": "x"}], schema=s).passed
    assert not check_schema([{"id": "nope", "content": 2}], schema=s).passed


def test_cross_module_agrees_and_disagrees():
    agree = [
        {"id": 1, "storage": {"content": "a"}, "tensor": {"content": "a"}},
        {"id": 2, "storage": {"content": "b"}, "tensor": {"content": "b"}},
    ]
    assert check_cross_module(agree).passed
    disagree = [
        {"id": 1, "storage": {"content": "a"}, "tensor": {"content": "z"}},
    ]
    r = check_cross_module(disagree)
    assert not r.passed and r.metric < 1.0


def test_id_stability():
    recs = [{"id": i} for i in range(10)]
    assert check_id_stability(records=recs, reload_ids=list(range(10))).passed
    r = check_id_stability(records=recs, reload_ids=[0, 1, 999])
    assert not r.passed


def test_faithfulness_grounded_and_wayward():
    srcs = ["the quick brown fox jumps over the lazy dog"]
    grounded = ["the quick brown fox"]
    wayward = ["quantum teleportation of synthetic marmalade"]
    assert check_faithfulness([srcs[0]], [grounded[0]]).passed
    assert not check_faithfulness([srcs[0]], [wayward]).passed


def test_identity_preserved():
    probe = {"honesty": True, "rigor": True}
    r = check_identity_preserved(persona_probe=probe,
                                 expected_traits=["honesty", "rigor"],
                                 drift_scores={"a": 0.05})
    assert r.passed


def test_consistency_span_repeatable():
    outs = ["the same answer", "the same answer", "the same answer"]
    assert check_consistency_span(outs).passed


def test_not_verbatim_flags_copy():
    src = " ".join(f"w{i}" for i in range(20))
    assert not check_not_verbatim([src], [src]).passed
    rewritten = " ".join([f"x{i}" for i in range(10)] + src.split()[10:])
    r = check_not_verbatim([src], [rewritten])
    assert r.passed


def test_integration_fuse_penalizes_mismatch():
    good = ok(check_round_trip, records=[{"id": 1, "c": "x"}],
              read_back=[{"id": 1, "c": "x"}])
    bad = ok(check_faithfulness, sources=["abcdefghijklmnopqrstuvwxyz"],
             synthesized=["quantum marmalade teleportation"])
    r = integration_accuracy(good, bad)
    assert r.metric < 0.7


def test_harness_runs_and_tolerates_broken_check():
    h = Harness("probe")
    s = h.suite(Phase.INFO_HANDLING, "ih")
    s.add("fine", lambda **kw: CheckResult(check="fine", passed=True, metric=1.0))
    s.add("boom", lambda **kw: (_ for _ in ()).throw(RuntimeError("kaboom")))
    results = h.run()
    by = {r.check: r for r in results}
    assert by["fine"].passed
    assert by["boom"].status == "error"
    assert h.summary()["failed"] == 1


def test_run_project_demo_is_deterministic(tmp_path):
    h1, r1, f1 = run_project("demo", str(tmp_path))
    h2, r2, f2 = run_project("demo", str(tmp_path))

    def _no_duration(rows):
        out = []
        for x in rows:
            d = x.to_dict()
            d.pop("duration_ms", None)
            out.append(d)
        return out

    assert _no_duration(r1 + f1) == _no_duration(r2 + f2)


@pytest.mark.parametrize("name", ALL)
def test_run_project_all(name, tmp_path):
    h, results, fused = run_project(name, str(tmp_path))
    assert len(results) == 10
    assert h.summary()["total_checks"] == len(results) + len(fused)


def test_humanizer_produces_numbered_prose():
    cr = CheckResult(check="provenance_traceable", passed=True, metric=1.0,
                     trace={"n": 42, "traceable": 42})
    text = Humanizer().describe(cr)
    assert "42" in text


def test_airadio_rates_machine_text_low():
    ai = AiRadio()
    robotic = ("Moreover, additionally, furthermore, moreover, moreover, we "
               "delve into leveraging seamless robust synergy, and moreover, "
               "additionally, we conclude, and lastly, moreover.")
    score = ai.score(robotic)
    assert score.human_index < 0.6


def test_airadio_rates_plain_text_higher():
    text = (
        "I checked the records twice and they all agree. The numbers held up. "
        "There were a couple of surprises, but nothing that changed the story.")
    assert AiRadio().score(text).human_index > 0.6


def test_fused_report_tags_integration_phase():
    h, results, fused = run_project("demo", ".")
    for f in fused:
        assert f.phase == Phase.DATA_INTEGRATION
    assert fused_report  # imported and callable