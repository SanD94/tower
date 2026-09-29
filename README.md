# Tower

Tower is an experimental representation compiler for codebases. It turns exact
`rg` and Git evidence into bounded, inspectable views without inventing semantic
relationships.

## Quick start

Requirements: Python 3.11+, Git, [ripgrep](https://github.com/BurntSushi/ripgrep), and [jq](https://jqlang.github.io/jq/).

Install the `tower` CLI into `~/.local/bin` (re-run after moving the repository):

```sh
./install.sh
```

```sh
tower status
tower index --root . --output .tower/evidence.jsonl
tower search 'View = compile' --evidence .tower/evidence.jsonl
```

The JSON Lines file records the evidence observed by `tower index`, using Git
blob OIDs for content identity. Later worktree edits do not overwrite that
evidence: `search` and `evidence` mark affected records stale, while `compile`
requires re-indexing so the question is answered again. Saved Representation IR
files remain immutable and report when their recorded input frame is stale.

Build and read a representation:

```sh
tower map \
  --evidence .tower/evidence.jsonl \
  --question "Where is the compiler contract defined?" \
  --intent locate-evidence \
  --term 'View = compile' \
  --focus . \
  --viewpoint topology \
  --detail summary \
  --budget-units 8 \
  --output .tower/view.json
```

Run `tower <command> --help` for command options; without installing, the same
commands run as `python -m tower` from a checkout. List the questions recorded
in saved views:

```sh
tower views
```

Tower is a proof of
concept; artifact formats may change. See [the description](docs/DESCRIPTION.md)
for the model and [the milestones](docs/MILESTONE.md) for current scope.

Reproduce the pinned baseline and Tower-assisted evaluation with the tasks,
rubrics, session format, and commands in
[`experiments/tower/`](experiments/tower/README.md).

## Agent use

Agents should start with [`AGENTS.md`](AGENTS.md). Prefer JSON output, retain the
generated evidence and view files, inspect omissions and diagnostics, and resolve
important claims back to evidence IDs rather than treating labels as facts.

## Development

```sh
python -m unittest discover -v
```
