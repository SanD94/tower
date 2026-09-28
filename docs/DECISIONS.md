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

## First end-to-end representation compiler — continue

The `compile` and `map` commands turn one evidence snapshot into bounded,
provenance-backed Representation IR. Explicit terms determine relevance, focus
anchors the subject, topology and evidence-list viewpoints produce different
typed connections, evidence detail exposes source records, and the unit budget
records every excluded candidate as an omission. Saved views render without
recompilation, while `explain` reports why visible and omitted units received
their decisions. Continue to cross-file and historical evidence without adding
semantic relationships that `rg` and Git cannot support.

Repeat the experiment with:

```sh
python -m tower index --root . --output .tower/evidence.jsonl
python -m tower compile \
  --evidence .tower/evidence.jsonl \
  --question "Where are the compiler and client responsibilities described?" \
  --intent locate-evidence \
  --term compiler --term client \
  --focus docs/DESCRIPTION.md \
  --viewpoint topology \
  --detail summary \
  --budget-units 7 \
  --output .tower/view.json
python -m tower map --view .tower/view.json
python -m tower explain <unit-id> --view .tower/view.json
```

## Cross-file and historical evidence — continue

The evidence and change viewpoints answer which Tower files and revisions define
search evidence by combining exact `rg` occurrences with inspectable Git commits,
diffs, changed-file sets, and current-line attribution. Containment, matching,
change, and attribution remain observed relationships; co-change alone is emitted
as `changed-with` with `historical-inference` status. Unsupported causal and
ownership viewpoints produce diagnostics instead of semantic guesses. A bounded
Tower-on-Tower run retained the source and history context that fit and recorded
the remaining relevant units as budget omissions. Continue to local
transformations without adding syntax-aware analysis or upgrading textual and
historical proximity into dependency claims.

Repeat the experiment with:

```sh
python -m tower index --root . --output .tower/evidence.jsonl
python -m tower compile \
  --evidence .tower/evidence.jsonl \
  --question "Which Tower files and revisions define how search evidence is collected and inspected?" \
  --intent locate-evidence \
  --term "search evidence" --term "rg --json" \
  --focus . \
  --viewpoint change \
  --detail evidence \
  --budget-units 25 \
  --output .tower/change-view.json
python -m tower map --view .tower/change-view.json
python -m tower evidence <commit-id> --evidence .tower/evidence.jsonl
```
