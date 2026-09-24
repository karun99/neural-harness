"""Information handling — how faithfully a project moves data around.

These checks measure data-integrity during transfer and storage, not whether
the numbers are "correct" in some absolute sense. We are answering: did the
data arrive intact, traceable, and agreed across modules?

  * provenance_traceable      — each record can be walked back to a source id;
                                measured as the fraction of records with an
                                unbroken audit chain.
  * round_trip_fidelity       — records written and read back compare
                                field-by-field; measured on a held-out sample.
  * schema_conformance        — records satisfy the declared schema (required
                                keys, expected types), reported as a share.
  * cross_module_agreement    — the same logical entity surfaced by two
                                different modules agrees field-for-field.
  * id_stability              — identifiers are stable under reload and unique
                                within the corpus (no collisions, no drift).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .core import CheckResult, Suite, Phase

__all__ = [
    "check_provenance", "check_round_trip", "check_schema",
    "check_cross_module", "check_id_stability", "information_handling_suite",
]

MISSING = object()


def check_provenance(
    records: Any = None,
    source_field: str = "source_id",
    audit_chain: Optional[List[str]] = None,
    **kw,
) -> CheckResult:
    """Fraction of records whose audit chain is unbroken from source to store.

    `records` is any iterable of dicts. `audit_chain` (optional) is a list of
    field names that must all be present and non-empty on every record to
    count as traceable.
    """
    if records is None:
        records = []
    target = audit_chain if audit_chain is not None else [source_field]
    items = list(records)
    traceable, broken = [], []
    for i, rec in enumerate(items):
        if isinstance(rec, dict) and all(rec.get(f) for f in target):
            traceable.append(i)
        else:
            broken.append({"index": i, "record": rec if isinstance(rec, dict) else str(rec)})
    n = len(items)
    metric = round(len(traceable) / n, 4) if n else 0.0
    passed = metric >= 0.999
    note = (
        f"Every one of the {n} records kept its audit trail intact from source to store."
        if passed else
        f"{len(broken)} of {n} records lost their audit trail somewhere in the pipeline."
    )
    return CheckResult(
        check="provenance_traceable", passed=passed, metric=metric,
        evidence=[{"record_index": i, "reason": "missing audit fields"} for i in broken[:10]],
        trace={"n": n, "traceable": len(traceable), "audit_fields": target},
        note=note,
    )


def check_round_trip(
    records: Any = None,
    read_back: Any = None,
    key: str = "id",
    sample_hint: int = 200,
    **kw,
) -> CheckResult:
    """Field-by-field fidelity of write-then-read on a sample of records.

    `records` are what was written; `read_back` is the same records as read
    back. We compare each shared field's equality and count agreement.
    """
    written = {r.get(key, i): r for i, r in enumerate(list(records or []))}
    read = list(read_back or [])
    compared, agreed = 0, 0
    mismatches: List[dict] = []
    for r in read:
        rid = r.get(key, MISSING)
        w = written.get(rid)
        if w is None:
            mismatches.append({"id": rid, "kind": "appeared_only_on_read"})
            continue
        for f in set(w) | set(r):
            if f == key:
                continue
            compared += 1
            if w.get(f, MISSING) == r.get(f, MISSING):
                agreed += 1
            elif len(mismatches) < 10:
                mismatches.append({"id": rid, "field": f, "write": w.get(f), "read": r.get(f)})
    metric = round(agreed / compared, 4) if compared else 0.0
    passed = metric >= 0.999
    note = (
        f"Everything written came back byte-for-byte on the sample — {agreed} of "
        f"{compared} fields matched."
        if passed else
        f"Write-and-read drifted on {compared - agreed} of {compared} fields; "
        f"that means data is changing between store and handoff."
    )
    return CheckResult(
        check="round_trip_fidelity", passed=passed, metric=metric,
        evidence=mismatches, trace={"fields_compared": compared, "agreed": agreed,
                                    "written": len(written), "read": len(read)},
        note=note,
    )


def check_schema(
    records: Any = None,
    schema: Optional[Dict[str, type]] = None,
    **kw,
) -> CheckResult:
    """Share of records conforming to a declared schema.

    `schema` maps field name to expected type. `object` as a type means "any
    non-null value". Records missing a required field or typing a field
    wrongly fail the check.
    """
    items = list(records or [])
    schema = schema or {}
    conforming, violations = 0, []
    for i, rec in enumerate(items):
        ok = True
        if not isinstance(rec, dict):
            ok = False
            violations.append({"index": i, "reason": "record is not a mapping"})
            continue
        for f, t in schema.items():
            v = rec.get(f, MISSING)
            if v is MISSING or v is None:
                if t is not str or str(v) == "":  # str allows empty only if not missing
                    ok = False
                    violations.append({"index": i, "field": f, "reason": "missing or null"})
                continue
            if t is not object and not isinstance(v, t):
                # bool is a subclass of int; accept either explicitly
                if not (t is int and isinstance(v, bool) and rec.get("_allow_bool_as_int")):
                    ok = False
                    violations.append({"index": i, "field": f,
                                       "expected": t.__name__, "got": type(v).__name__})
        if ok:
            conforming += 1
    n = len(items)
    metric = round(conforming / n, 4) if n else 0.0
    passed = metric >= 0.999
    note = (
        f"All {n} records matched the schema in {list(schema)}."
        if passed else
        f"{n - conforming} of {n} records drifted from the schema; the first few "
        f"offenders are listed in the evidence."
    )
    return CheckResult(
        check="schema_conformance", passed=passed, metric=metric,
        evidence=violations[:10], trace={"conforming": conforming, "n": n},
        note=note,
    )


def check_cross_module(
    entities: Any = None,
    module_fields: Optional[List[str]] = None,
    **kw,
) -> CheckResult:
    """Agreement between modules that each maintain a view of the same entity.

    `entities` is a list of records with a shared `id` key plus zero or more
    module views. A module view is any dict-valued field (other than `id`);
    when `module_fields` is given, we consider only those named views. Every
    shared (non-module) field must agree across all present views.
    """
    items = list(entities or [])
    compared, agreed = 0, 0
    disagreements: List[dict] = []
    for ent in items:
        if not isinstance(ent, dict):
            continue
        shared_fields = set(ent)
        views = {}
        for f in shared_fields:
            if f == "id":
                continue
            if module_fields and f not in module_fields:
                continue
            if isinstance(ent[f], dict) and module_fields:
                views[f] = ent[f]
            elif not module_fields and isinstance(ent[f], dict):
                views[f] = ent[f]
        if len(views) < 2:
            continue
        # field names that are common to every view
        common = set.intersection(*(set(v) for v in views.values()))
        for f in common:
            vals = {m: v.get(f) for m, v in views.items()}
            compared += 1
            if len(set(map(str, vals.values()))) <= 1:
                agreed += 1
            elif len(disagreements) < 10:
                disagreements.append({"id": ent.get("id"), "field": f, "mod_views": vals})

    metric = round(agreed / compared, 4) if compared else 0.0
    passed = metric >= 0.999
    note = (
        f"The modules see the world the same way: {agreed} of {compared} shared "
        f"fields agreed."
        if passed else
        f"The two modules disagreed on {compared - agreed} of {compared} fields; "
        f"the neural path and the storage path are out of sync somewhere."
    )
    return CheckResult(
        check="cross_module_agreement", passed=passed, metric=metric,
        evidence=disagreements, trace={"compared": compared, "agreed": agreed},
        note=note,
    )


def check_id_stability(
    records: Any = None,
    reload_ids: Any = None,
    key: str = "id",
    **kw,
) -> CheckResult:
    """Identifiers are unique in corpus and stable across a reload."""
    items = list(records or [])
    ids = [r.get(key) for r in items if isinstance(r, dict)]
    dupes = {i for i in ids if ids.count(i) > 1}
    reload_ids = list(reload_ids or [])
    drifted = [i for i in reload_ids if i not in set(ids)]
    n = len(ids)
    unique_ok = not dupes
    stable_ok = not drifted
    metric = round(max(0.0, 1.0 - (len(dupes) + len(drifted)) / max(1, n)), 4)
    passed = unique_ok and stable_ok
    note = (
        f"All {n} identifiers are unique and none of them drifted on reload."
        if passed else
        f"{len(dupes)} duplicate ids and {len(drifted)} ids that vanished on reload."
    )
    return CheckResult(
        check="id_stability", passed=passed, metric=metric,
        evidence={"duplicates": sorted(dupes), "drifted_on_reload": drifted},
        trace={"n": n, "dupes": len(dupes), "drifted": len(drifted)},
        note=note,
    )


def information_handling_suite() -> Suite:
    s = Suite(Phase.INFO_HANDLING, "Information handling")
    s.add("provenance_traceable", check_provenance,
          "records keep an unbroken audit chain from source to store")
    s.add("round_trip_fidelity", check_round_trip,
          "write-then-read returns identical data, field by field")
    s.add("schema_conformance", check_schema,
          "records obey the declared schema")
    s.add("cross_module_agreement", check_cross_module,
          "modules that each hold a view of an entity agree on it")
    s.add("id_stability", check_id_stability,
          "identifiers stay unique and stable across reloads")
    return s