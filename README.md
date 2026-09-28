# Tower

Tower is an experimental representation compiler for codebases. It turns exact
`rg` and Git evidence into bounded, inspectable views without inventing semantic
relationships.

## Quick start

Requirements: Python 3.11+, Git, and [ripgrep](https://github.com/BurntSushi/ripgrep).

Install the `tower` CLI into `~/.local/bin` (re-run after moving the repository):

```sh
./install.sh
```

```sh
tower status
tower index --root . --output .tower/evidence.jsonl
tower search 'View = compile' --evidence .tower/evidence.jsonl
```

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
commands run as `python -m tower` from a checkout. Tower is a proof of
concept; artifact formats may change. See [the description](docs/DESCRIPTION.md)
for the model and [the milestones](docs/MILESTONE.md) for current scope.

## Agent use

Agents should start with [`AGENTS.md`](AGENTS.md). Prefer JSON output, retain the
generated evidence and view files, inspect omissions and diagnostics, and resolve
important claims back to evidence IDs rather than treating labels as facts.

## Development

```sh
python -m unittest discover -v
```
