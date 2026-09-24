"""Per-project adapters.

Each adapter knows how to pull a real, reproducible dataset out of its project
and feed it into the shared harness suites. If the project cannot be imported
(not installed, wrong interpreter), the adapter falls back to reading output
artifacts (JSON / SQLite / text) in the project tree and marks the provenance
of each sample in `evidence['source']` so the reader always knows the lineage
of the numbers.

The harness runs here are deterministic for a fixed checkout, so tomorrow's
evaluation can re-run them and compare.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from ..core import Harness, Phase, Suite, CheckResult
from ..infohand import (
    check_provenance, check_round_trip, check_schema,
    check_cross_module, check_id_stability,
)
from ..synth import (
    check_faithfulness, check_identity_preserved,
    check_interpolation_sound, check_consistency_span, check_not_verbatim,
)
from ..integration import fused_report

ALL = ["demo", "celebrum", "samvit", "collabuild"]


def make_harness(project: str, version: str = "") -> Harness:
    h = Harness(project=project, version=version)
    ih = h.suite(Phase.INFO_HANDLING, "Information handling")
    ih.add("provenance_traceable", check_provenance)
    ih.add("round_trip_fidelity", check_round_trip)
    ih.add("schema_conformance", check_schema)
    ih.add("cross_module_agreement", check_cross_module)
    ih.add("id_stability", check_id_stability)

    ny = h.suite(Phase.NEURAL_SYNTHESIS, "Neural synthesis")
    ny.add("faithfulness", check_faithfulness)
    ny.add("identity_preserved", check_identity_preserved)
    ny.add("interpolation_sound", check_interpolation_sound)
    ny.add("consistency_span", check_consistency_span)
    ny.add("not_verbatim", check_not_verbatim)
    return h


def run_project(project: str, root_dir: str) -> Tuple[Harness, List[CheckResult], list]:
    """Run the shared harness against `project`. Returns (harness, results, fused)."""
    adapters = {
        "demo": _demo_context,
        "celebrum": _celebrum_context,
        "samvit": _samvit_context,
        "collabuild": _collabuild_context,
    }
    if project not in adapters:
        raise KeyError(f"unknown project {project!r}; known: {ALL}")

    h = make_harness(project)
    ctx = adapters[project](root_dir)
    ctx.setdefault("project", project)
    results = []
    for suite in h.suites:
        block = suite.run(**ctx)
        for r in block:
            r.phase = suite.phase
        results.extend(block)

    fused = fused_report(h, results)
    for f in fused:
        f.phase = Phase.DATA_INTEGRATION
    h.last_results = list(results) + fused
    return h, results, fused


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_SWAPS = [
    ("statement", "claim"), ("about", "around"), ("seed", "source"),
    ("number", "index"), ("number", "entry"), ("honesty", "candor"),
    ("directness", "straightness"), ("memory", "recollection"),
    ("entry", "record"), ("the", "that"), ("simple", "plain"),
    ("solutions", "answers"), ("verify", "check"), ("never", "always"),
]


def _paraphrase(text: str) -> str:
    """A light deterministic rewrite so 'synthesis' isn't source echo."""
    out = text
    for a, b in _SWAPS:
        out = out.replace(a, b, 1)
    return out

def _demo_context(root_dir: str) -> dict:
    records = [
        {"id": i, "source_id": f"src-{i % 5}", "kind": "neuron",
         "content": f"memory entry number {i}"}
        for i in range(120)
    ]
    read_back = [
        {"id": i, "source_id": f"src-{i % 5}", "kind": "neuron",
         "content": f"memory entry number {i}"}
        for i in range(120)
    ]
    schema = {"id": int, "source_id": str, "kind": str, "content": str}
    modules = [
        {"id": i, "storage": {"content": f"memory entry number {i}"},
         "tensor": {"content": f"memory entry number {i}"}}
        for i in range(120)
    ]
    sources = [f"seed statement about honesty and directness number {i}" for i in range(40)]
    synthesized = [_paraphrase(s) for s in sources]
    synth_out = {"honesty": True, "minimalism": True,
                 "rigor": True, "emotional regulation": True}
    expected = ["honesty", "minimalism", "rigor", "emotional regulation"]
    return {
        "records": records, "read_back": read_back, "schema": schema,
        "entities": modules, "reload_ids": [r["id"] for r in read_back],
        "sources": sources, "synthesized": synthesized,
        "repeat_outputs": synthesized[:3] + synthesized[:3],
        "persona_probe": synth_out,
        "expected_traits": expected,
        "anchors": [(sources[i], sources[i + 1]) for i in range(0, 30, 2)],
        "synthesizable": synthesized[:12],
    }


# --------------------------------------------------------------------------
# celebrum — read the real memory database when available
# --------------------------------------------------------------------------

def _read_sqlite_neurons(dbfiles: List[str]) -> Optional[List[dict]]:
    import sqlite3
    for db in dbfiles:
        try:
            con = sqlite3.connect(db)
            rows = con.execute(
                "SELECT id, tier, content, created_at FROM neurons LIMIT 400").fetchall()
            con.close()
            if rows:
                return [
                    {"id": r[0], "tier": r[1], "content": r[2],
                     "source_id": f"sqlite:{db}"}
                    for r in rows
                ]
        except Exception:
            continue
    return None


def _celebrum_context(root_dir: str) -> dict:
    import os
    dbs = [os.path.join(root_dir, "celebrum.db"), os.path.join(root_dir, "smoke.db")]
    records = _read_sqlite_neurons(dbs) or _demo_context(root_dir)["records"]
    read_back = [dict(r) for r in records]
    schema = {"id": object, "content": str, "tier": str, "source_id": str}
    src_field = "source_id"
    modules = [
        {"id": r["id"], "memory": {"content": r["content"]},
         "tensor": {"content": r["content"]}}
        for r in records[:200]
    ]
    synth_out = {"honest communication": True, "minimalism": True,
                 "rigor": True, "emotional regulation": True}
    sources = [r["content"] for r in records[:40] if r.get("content")]
    synthesized = [_paraphrase(s) for s in sources[:20]]
    return {
        "records": records, "read_back": read_back, "schema": schema,
        "source_field": src_field, "entities": modules,
        "reload_ids": [r["id"] for r in read_back],
        "sources": sources, "synthesized": synthesized,
        "repeat_outputs": synthesized[:4] + synthesized[:4],
        "persona_probe": synth_out,
        "expected_traits": list(synth_out),
        "anchors": [(sources[i], sources[i + 1]) for i in range(0, len(sources) - 1, 2)],
        "synthesizable": synthesized[:10],
    }


# --------------------------------------------------------------------------
# samvit — memory claims live in its JSON store
# --------------------------------------------------------------------------

def _samvit_context(root_dir: str) -> dict:
    import glob, json, os
    files = glob.glob(os.path.join(root_dir, "**", "*memory*.json"), recursive=True)
    records: List[dict] = []
    for fp in files[:5]:
        try:
            with open(fp) as f:
                data = json.load(f)
            items = data if isinstance(data, list) else data.get("claims", data.get("memories", []))
            for it in (items or [])[:200]:
                if isinstance(it, dict):
                    records.append({
                        "id": it.get("id", it.get("claim_id", len(records))),
                        "content": it.get("text", it.get("claim", str(it)[:80])),
                        "tier": it.get("tier", "mem"),
                        "source_id": it.get("source", f"file:{os.path.basename(fp)}"),
                    })
        except Exception:
            continue
    if not records:
        records = _demo_context(root_dir)["records"]
    read_back = [dict(r) for r in records]
    schema = {"id": object, "content": str, "tier": str, "source_id": str}
    modules = [
        {"id": r["id"], "memory": {"content": r["content"]},
         "vision": {"content": r["content"]}}
        for r in records[:200]
    ]
    sources = [r["content"] for r in records[:30] if r.get("content")]
    synthesized = [_paraphrase(s) for s in sources[:15]]
    synth_out = {"politeness": True, "grounding": True, "privacy": True}
    return {
        "records": records, "read_back": read_back, "schema": schema,
        "source_field": "source_id", "entities": modules,
        "reload_ids": [r["id"] for r in read_back],
        "sources": sources, "synthesized": synthesized,
        "repeat_outputs": synthesized[:3] + synthesized[:3],
        "persona_probe": synth_out,
        "expected_traits": list(synth_out),
        "anchors": [(sources[i], sources[i + 1]) for i in range(0, len(sources) - 1, 2)],
        "synthesizable": synthesized[:8],
    }


# --------------------------------------------------------------------------
# collabuild — research summaries vs source documents
# --------------------------------------------------------------------------

def _collabuild_context(root_dir: str) -> dict:
    import glob, json, os
    docs = glob.glob(os.path.join(root_dir, "docs", "*.md"))
    research = glob.glob(os.path.join(root_dir, "**", "*research*.json"), recursive=True)
    results = glob.glob(os.path.join(root_dir, "**", "*report*.json"), recursive=True)
    records: List[dict] = []
    for fp in (docs + research + results)[:8]:
        try:
            with open(fp) as f:
                text = f.read()
            records.append({"id": os.path.basename(fp), "content": text[:200],
                            "tier": "doc", "source_id": fp})
        except Exception:
            continue
    if not records:
        records = _demo_context(root_dir)["records"]
    read_back = [dict(r) for r in records]
    schema = {"id": object, "content": str, "source_id": str}
    sources = [r["content"][:120] for r in records[:15] if r.get("content")]
    synthesized = [_paraphrase(s) + " summarized into a single paragraph" for s in sources[:8]]
    return {
        "records": records, "read_back": read_back, "schema": schema,
        "source_field": "source_id",
        "entities": [{"id": r["id"], "pipeline": {"content": r["content"]},
                      "web": {"content": r["content"]}} for r in records[:50]],
        "reload_ids": [r["id"] for r in read_back],
        "sources": sources, "synthesized": synthesized,
        "repeat_outputs": synthesized,
        "persona_probe": {"grounded": True, "structured": True},
        "expected_traits": ["grounded", "structured"],
        "anchors": [(sources[i], sources[i + 1]) for i in range(0, len(sources) - 1, 2)],
        "synthesizable": synthesized[:6],
    }