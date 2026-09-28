# Tower agent guide

Tower gives agents a bounded, provenance-bearing view of a Git repository. It is
deterministic: the question is descriptive, while each repeated `--term` supplies
the exact relevance vocabulary.

## Use Tower

From the repository being investigated (with Tower installed or on `PYTHONPATH`):

```sh
python -m tower index --root . --output .tower/evidence.jsonl --json
python -m tower compile \
  --evidence .tower/evidence.jsonl \
  --question "Where is this behavior defined?" \
  --intent locate-evidence \
  --term behavior --term contract \
  --focus . \
  --viewpoint topology \
  --detail summary \
  --budget-units 10 \
  --output .tower/view.json
python -m tower map --view .tower/view.json
```

Use `evidence <id> --json` to resolve source claims and `explain <unit-id>` to
inspect inclusion or omission decisions. Use `refine`, `trace`, `project`, and
`collapse` to transform a saved view without recompiling it. Use
`views --json` to list the questions recorded in saved views under `.tower`.
Never infer calls,
ownership, or causality from textual or historical proximity; Tower reports only
the relationships supported by its collected evidence.

## Work on Tower

- Require Python 3.11+, Git, `rg`, and `jq`.
- Keep the PoC standard-library-only and its JSON artifacts inspectable.
- Preserve provenance, explicit omissions, and deterministic output.
- Run `python -m unittest discover -v` before submitting changes.
- Read `docs/DESCRIPTION.md` for the compiler contract and `docs/MILESTONE.md` for
  scope; do not add deferred systems without evidence from an experiment.
