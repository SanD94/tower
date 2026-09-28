# Experiment decisions

## Walking CLI — continue

The minimal Python CLI can identify a Git workspace and exact revision from either
the repository root or a nested path, distinguish a dirty working copy, and list
the searchable files selected by `rg`. Its versioned JSON output is sufficient to
identify the evidence source for the next snapshot experiment. Continue to the
inspectable-evidence slice without adding another VCS backend or file-discovery
mechanism.

## Inspectable evidence — continue

The `index`, `search`, and `evidence` commands answer where Tower's compiler
contract is defined and expose the exact normalized source span and collector
provenance behind each result. Re-indexing an unchanged workspace produces the
same JSON Lines snapshot, while a source edit marks evidence from only that file
as stale. The experiment supports continuing to the first representation
compiler without adding a database or replacing `rg`.

Repeat the experiment with:

```sh
python -m tower index --root . --output .tower/evidence.jsonl
python -m tower search 'View = compile' --evidence .tower/evidence.jsonl
python -m tower evidence <id> --evidence .tower/evidence.jsonl
```
