# Experiment decisions

## Walking CLI — continue

The minimal Python CLI can identify a Git workspace and exact revision from either
the repository root or a nested path, distinguish a dirty working copy, and list
the searchable files selected by Git. Its versioned JSON output is sufficient to
identify the evidence source for the next snapshot experiment. Continue to the
inspectable-evidence slice without adding another VCS backend.

## Inspectable evidence — continue

The `index`, `search`, and `evidence` commands answer where Tower's compiler
contract is defined and expose the exact normalized source span and collector
provenance behind each result. Re-indexing an unchanged workspace produces the
same JSON Lines evidence. Edited or deleted source marks only the affected
recorded evidence stale instead of deleting the evidence that supported an
earlier answer. The experiment supports continuing to the first representation
compiler without adding a database or replacing `rg`.

Repeat the experiment with:

```sh
python -m tower index --root . --output .tower/evidence.jsonl
python -m tower search 'View = compile' --evidence .tower/evidence.jsonl
python -m tower evidence <id> --evidence .tower/evidence.jsonl
```

## Git-authoritative evidence identity — revise

Git now owns revision, file-set, ignore, and byte-content identity. Tower uses
`git ls-files --cached --others --exclude-standard` for discovery and
`git hash-object` blob OIDs for tracked, modified, and untracked files. The JSON
Lines index is recorded evidence, replaced only by an explicit `index` command.
Search and inspection preserve old evidence and compare its blob identities with
the worktree; compilation refuses stale input so a changed question must be
answered from newly indexed evidence. Tower IDs remain contextual for file
occurrences, spans, units, connections, and omissions, so equal blobs at
different paths do not collapse. Saved Representation IR remains immutable,
records its source revision and worktree identities, and reports when that frame
is stale. Continue without a database, daemon, or Tower-owned branch state.

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

## Local transformations — continue

The `refine`, `trace`, `project`, and `collapse` commands now rewrite saved
Representation IR without recompiling evidence. Refinement promotes only the
omitted units reachable from the selected boundary and applies its own detail and
visible-unit budget. Existing units, typed connections, subject, and boundary
ports remain unchanged. Collapse restores the original boundary view exactly,
apart from the appended history that records the inverse rewrite. Trace and
project record every filtered unit and connection as an omitted claim. Continue
to a dogfooding evaluation; the local rewrite contract is useful without
introducing syntax-aware evidence or another representation store.

Repeat the experiment with:

```sh
python -m tower compile \
  --evidence .tower/evidence.jsonl \
  --question "Where are local representation transformations defined?" \
  --intent locate-evidence \
  --term refine --term collapse \
  --focus tower/representation.py \
  --viewpoint topology \
  --detail summary \
  --budget-units 4 \
  --output .tower/local-view.json
python -m tower refine <unit-id> \
  --view .tower/local-view.json --detail evidence --budget-units 5 \
  --output .tower/refined-view.json
python -m tower trace <unit-id> \
  --view .tower/refined-view.json --output .tower/traced-view.json
python -m tower project contains \
  --view .tower/refined-view.json --output .tower/projected-view.json
python -m tower collapse <region-id> \
  --view .tower/refined-view.json --output .tower/collapsed-view.json
```

## Repeatable dogfooding evaluation — continue to an agent observer

Three public tasks pin revision `44cd9895d9ed83b40a828b0401b072c013907d95`
and keep their ground-truth claims, required conditions, source spans,
distractors, and rubrics outside indexed evidence. The `session-start`,
`session-record`, `session-submit`, `score`, and `compare` commands produce
atomic, inspectable JSON and reject revision mismatches or incomplete
assessments.

The first compiler-input pilot scored both ordinary-tools and Tower-assisted
answers at 12/12 with no incorrect claims or omitted conditions. The Tower run
varied question, focus, viewpoint, detail, and budget one at a time and recorded
the resulting frame, subject, relationship, source-detail, and omission changes.
It used ten more recorded actions and 25.984589 fewer seconds. Because the same
implementation agent authored the task and rehearsed the Tower commands, those
measurements cannot support a causal accuracy or speed advantage. This
procedural run establishes reproducibility only. Continue to the bounded Amp
observer experiment: the compiler frame, explicit omissions, and resolvable
evidence were useful enough to test as agent context, and independent,
uninterrupted repetitions there must decide whether they improve outcomes.

Repeat the experiment with the instructions and artifacts under
`experiments/tower/`. Do not expose `ground-truth/` until the participant has
submitted an answer.
