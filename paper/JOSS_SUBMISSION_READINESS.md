# JOSS submission readiness — neural-harness

This file records, transparently, which of the JOSS gates are already met and
which still require time. It exists so the maintainer never submits believing
a gate is satisfied when it is not.

## Requirements already met

- **OSI-approved license**: `LICENSE` (MIT) is a plain-text OSI-approved license.
- **Open repository**: the software is hosted on GitHub under `karun99/neural-harness`, browsable and clonable without registration, with issues open to the public.
- **Obvious research application**: a validation harness for neural software (memory, persona, retrieval, synthesis). State-of-the-field and design sections in the paper frame the scientific contribution.
- **Installable packaging**: `pyproject.toml` with a console entry point (`nh`); `pip install .` works.
- **Automated tests**: `pytest` suite covers the core runner and every check; run via CI.
- **Documentation**: README with statement of need, install, usage, examples; `CONTRIBUTING.md` with contribution/support/issue guidelines; API docstrings throughout.
- **`paper.md` / `paper.bib`**: JOSS-format paper with the required sections (Summary, Statement of need, State of the field, Software design, Research impact statement, AI usage disclosure, References) and a bibliography.
- **AI usage disclosure**: present in README and paper per the JOSS AI usage policy.

## Gates that still need time (not yet met)

These are calendar- or evidence-bound and cannot be produced by a clean
checkout alone:

| Gate | Current status | What turns it green |
|---|---|---|
| Six months of public development history | Repo created recently; history is short | Keep developing publicly; a submission must show history spanning > 6 months with iterative commits, not a concentrated dump |
| Tagged releases / changelog | No tagged release yet | Cut `v1.0.0` once the API settles; keep a `CHANGELOG.md` |
| Demonstrated research impact | Used by the author's own projects (Celebrum, Samvit, Collabuild) | Document adoption externally: published preprints citing the harness, other groups' repos using `nh`, reproducible benchmark artifacts |
| Community engagement | No external issues/PRs yet | Public issue tracker is open; external contributions and discussions will accumulate |

## Suggested path to submission

1. Keep developing openly; ensure commits are spread over months.
2. Tag releases and maintain `CHANGELOG.md`.
3. Run `nh site --root ../` on release and publish the cross-project report.
4. When the six-month public-history gate is met and at least one external
   adoption signal exists, submit via the JOSS submission form.