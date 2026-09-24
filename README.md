# neural-harness

A validation harness engine for neural projects. It measures three things a
research reviewer actually checks:

1. **Information handling** — how faithfully a project moves data around
   (provenance, round-trip integrity, schema conformance, cross-module
   agreement, id stability).
2. **Neural synthesis** — how honestly a project generates new material
   (faithfulness to source, identity preservation, interpolation, consistency,
   non-verbatim output).
3. **Data integration** — whether the two lenses agree once fused, so
   "integrated accuracy" is a measured number rather than an assumption.

Every result is issued in two forms: a structured record (JSON, auditable,
evidence-first) and prose that reads as though a careful human wrote it. The
prose is graded by an AI-likeness detector (the **Human Voice Index**), so the
harness never ships machine-sounding reports about machines.

Standard library only, Python 3.9+, no model downloads, no API keys.

## Statement of need

Neural projects — memory graphs, persona models, retrieval pipelines, research
synthesizers — routinely claim accuracy in READMEs and demo screenshots, but
the claim is rarely reproducible. The numbers are usually hand-written after a
single run, they do not separate "data survived the pipeline" from "data was
regenerated honestly", and the reports read as templated AI output that nobody
can audit tomorrow.

`neural-harness` replaces that with a repeatable instrument:

- every score traces to a runnable check with recorded `evidence`;
- **information handling** and **neural synthesis** are measured separately,
  then **fused** into one data-integration accuracy so a strong storage layer
  cannot hide a weak generation layer (or vice versa);
- outcomes are deterministic for a fixed checkout, so an evaluation can be
  re-run by anyone at any time;
- prose reports are generated in a human voice and self-scored for AI
  tell-tales, which matters in a field that increasingly must disclose exactly
  how "AI-like" its own outputs are.

It is aimed at researchers who maintain a small-moderate neural software
project (memory systems, agent pipelines, synthesis toolkits) and need an
credible, inspectable validation story — for their own readers, for repos, or
for journal submission.

## Install

```sh
pip install .
# or, for development:
pip install -e ".[dev]"
```

Requires Python 3.9+. There are no runtime dependencies.

## Usage

Run the full harness for the built-in demo project:

```sh
nh validate demo
```

Run for a real project (the adapter pulls records from its own checkout):

```sh
nh validate celebrum   --root ../celebrum
nh validate samvit     --root ../samvit
nh validate collabuild --root ../collabuild
```

Run every project in a directory and write one combined report:

```sh
nh site --root /path/to/checkouts
```

Grade any text's human voice index:

```sh
nh voice "your text here"
nh voice --file report.md
```

Reports are written to `harness_reports/<project>.validation.json` (structured)
and `.md` (human-readable markdown). Each run appends to
`harness_reports/harness_history.jsonl`.

Reports include:

- overall accuracy across all checks;
- a separate integration-accuracy figure (the fused lens);
- per-check status, metric (0..1) and duration;
- the Human Voice Index with the specific AI-tell signals found, if any.

### Example report excerpt

```
celebrum finished its harness run with an overall accuracy of 0.76. 14 of 14
checks passed outright. Measured on data integration specifically, accuracy
came to 0.77.

In information handling we ran 5 checks. We walked back 120 records to their
sources and all of them survived the journey. Provenance holds. ...

[voice] human index 0.882 -> reads human
```

## Tests

```sh
python -m pytest
```

The suite covers the harness runner, the five information-handling checks, the
five synthesis checks, the fused integration score, the humanizer templates,
and the AiRadio voice grader.

## Contributing

Please read the contribution guide in [CONTRIBUTING.md](CONTRIBUTING.md). In
short:

- open an issue before opening a pull request;
- keep the package dependency-free and Python 3.9 compatible;
- every new check needs a deterministic test and a human-voice `note`;
- run `python -m pytest` and `nh voice --file <your-report>` before pushing.

## Support

Bug reports and feature requests belong in the GitHub issues tracker. For
general help, join a discussion under the Issues tab rather than emailing
maintainers directly.

## JOSS paper

The JOSS submission materials live in [`paper/`](paper/): `paper.md`,
`paper.bib`, plus `JOSS_SUBMISSION_READINESS.md`, which records which of the
JOSS gates are already met (license, tests, metadata, docs) and which still
need calendar time (six months of public history, tagged releases, external
research-adoption evidence).

## License

MIT — see [LICENSE](LICENSE).

## AI usage disclosure

Parts of this software, documentation and tests were drafted with generative
AI assistance (code generation and copy-editing). Every automated artifact was
reviewed and validated by a human maintainer, who made the design decisions.
This disclosure is maintained in line with the JOSS AI usage policy.