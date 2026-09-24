# Contributing to neural-harness

Thanks for wanting to help. This document keeps the repo small, dependency-free
and, most of all, honest about what each number means.

## Ground rules

- Keep the package **standard-library only** and **Python 3.9 compatible**.
- Open an issue before opening a pull request so the change gets discussed once
  and implemented once.
- Every new check needs:
  1. a deterministic test in `tests/`;
  2. an evidence-first `CheckResult` (numbers must be traceable);
  3. a human-voice `note` and a `Humanizer` voice entry in
     `neural_harness/humanize.py`.
- Run the graders before pushing:
  ```sh
  python -m pytest
  python -m neural_harness voice --file <your-report.md>
  ```
  A report that scores below our human-voice threshold should be rewritten,
  not force-committed.

## Adding a project adapter

1. Add a builder function in `neural_harness/projects/__init__.py` returning a
   harness context (records, read_back, schema, sources, synthesized, ...).
2. Register it in the `adapters` dict and the `ALL` list.
3. Fall back to output artifacts (JSON/SQLite/text) when the project is not
   importable; always record where the sample came from in `evidence`.

## Reporting bugs

Search the issues list first. If you open a new issue, include:

- the command you ran,
- the Python version,
- the first ~30 lines of the report,
- (if relevant) the `harness_history.jsonl` tail.

## Support expectations

This is maintained by a single maintainer in spare time. Issues are the
channel for help; expect answers within a week, not minutes.

## License

By contributing you agree that your contributions are licensed under the same
MIT license as the rest of the project.