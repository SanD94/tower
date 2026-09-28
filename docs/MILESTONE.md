# Milestones

Tower is developed as a sequence of executable proofs of concept. The Tower repository is the initial corpus: after each slice exists, it is used to investigate the next slice. This dogfooding loop keeps the backend useful before a graphical client exists and exposes representation problems while the system is still small enough to change freely.

Every milestone must end with:

- A question about Tower that can be investigated with the resulting executable.
- A repeatable command sequence and inspectable artifacts.
- Tests for the behavior introduced by the milestone.
- A short continue, revise, or stop decision.

The milestones are experiments, not a product roadmap. Formats may be replaced while the PoC remains experimental. The backend deliberately uses only `rg`, Git, and optional `fzf`; do not add a parser, language server, database, daemon, plugin framework, or client capability before an experiment proves that the minimal tools are insufficient.

## Compiler contract

The milestones converge on one contract:

```text
View = compile(Evidence, Question, Focus, Viewpoint, Detail, Budget)
```

Each input must have an observable effect:

- **Evidence** supplies the versioned facts and provenance that compilation is allowed to use.
- **Question** states the information need and influences relevance. In the deterministic PoC it includes plain text, an explicit intent, and explicit search terms rather than pretending that unrestricted natural-language understanding already exists.
- **Focus** anchors compilation to stable subjects in the evidence graph.
- **Viewpoint** selects which relationship meanings and representation forms are useful for the question.
- **Detail** controls explanatory granularity: summary, mechanism, or evidence—not graphical magnification.
- **Budget** is a structured set of hard limits. The first PoC supports maximum visible units; excluded relevant material must be recorded as omissions rather than silently discarded.

The resulting **View** is Representation IR, not a screen layout. It contains the complete frame, visible units, typed connections, provenance, omissions, and transformation history. Terminal and graphical renderers consume the same IR.

Early milestones may implement a deliberately narrow value for an input, but no input may remain decorative metadata. A milestone that cannot demonstrate how its supported inputs affect output has not implemented this contract.

## Backend PoCs

### Milestone 2: first end-to-end representation compiler

**Question:** Where are Tower's compiler and client responsibilities described, and how are those matches contained in the repository?

**PoC:**

```sh
python -m tower map \
  --evidence .tower/evidence.jsonl \
  --question "Where are the compiler and client responsibilities described?" \
  --intent locate-evidence \
  --term compiler --term client \
  --focus docs/DESCRIPTION.md \
  --viewpoint topology \
  --detail summary \
  --budget-units 7
```

Implementation:

- Use `rg` patterns to collect headings, exact terms, and surrounding text from Tower's documentation without parsing Markdown.
- Introduce only repository, file, heading/match, `contains`, and `matched-by` evidence needed by the question.
- Define Representation IR v1 and its JSON schema.
- Implement `compile` and `map` with all six compiler inputs represented explicitly.
- Resolve focus paths or IDs to stable evidence subjects.
- Use question terms and intent for deterministic relevance; make unsupported interpretation visible rather than guessed.
- Support topology and evidence-list viewpoints plus summary and evidence detail, so viewpoint and detail each have an observable effect.
- Implement text renderers and `tower explain` for inclusion and omission decisions.

Exit criteria:

- Changing the question changes relevance without changing the underlying evidence.
- Changing focus changes the anchored subject.
- Changing viewpoint, detail, or budget causes a defined and testable output change.
- Every visible unit and connection resolves to evidence.
- Budget overflow produces explicit omissions.
- The saved Representation IR can be rendered again without re-running compilation.

### Milestone 3: cross-file and historical evidence

**Question:** Which Tower files and revisions define how search evidence is collected and inspected?

**PoC:** compile a bounded evidence or change view from `rg` matches and Git history, then inspect every visible source span and commit.

Implementation:

- Collect question terms and exact occurrences with `rg --json`.
- Collect revision, log, diff, changed files, and line provenance with read-only Git commands.
- Introduce only relationships supported by those tools: containment, matched-by, changed-in, line-attributed-to, and changed-with.
- Mark changed-with as historical inference and textual occurrence as a match, never as a call, dependency, or cause.
- Add evidence and change viewpoints; unsupported causal or ownership viewpoints return diagnostics.
- Add fixture tests and golden Representation IR tests before compiling Tower itself.

Exit criteria:

- The evidence and change views answer the milestone question using Tower's own files and history.
- Every connection is either directly observed through `rg`/Git or visibly marked as historical inference.
- No textual mention or co-change is presented as a semantic dependency or causal claim.
- The result stays within budget and identifies evidence omitted by compression.

### Milestone 4: local transformations

**Question:** Can one part of a Tower evidence view be expanded and restored without losing the surrounding explanation?

**PoC:**

```sh
python -m tower refine <unit-id> --view <view.json>
python -m tower trace <unit-id> --view <view.json>
python -m tower project <relationship-type> --view <view.json>
python -m tower collapse <region-id> --view <refined-view.json>
```

Implementation:

- Implement `refine`, `trace`, `project`, and `collapse` as named rewrites over Representation IR.
- Preserve the original subject, external typed connections, and stable region ports.
- Record claims added, retained, and omitted by each rewrite.
- Make detail and budget apply locally as well as to initial compilation.

Exit criteria:

- Refining one region leaves its surroundings semantically unchanged.
- Collapsing restores an equivalent boundary representation.
- Transformation history explains every difference between saved views.

### Milestone 5: repeatable dogfooding evaluation

**Question:** Does Tower help a person understand an unfamiliar Tower change more accurately or with less navigation than ordinary tools?

**PoC:** run one pinned Tower investigation once with ordinary tools and once with the Tower CLI, then compare the two inspectable session records and scored answers.

Implementation:

- Pin Tower revisions that contain completed backend slices.
- Define several answerable tasks over those revisions without encoding their answers in compiler rules.
- Store ground-truth claims, required conditions, source spans, distractors, and answer rubrics separately from indexed evidence.
- Compare ordinary `rg`, editor, and Git investigation with deterministic Tower.
- Record queries, transformations, evidence opened, elapsed time, and submitted answers.
- Evaluate correctness and omitted conditions, not diagram attractiveness.

Exit criteria:

- Another person can reproduce both baseline and Tower-assisted sessions.
- At least one task exercises question, focus, viewpoint, detail, and budget independently.
- A written decision says whether the compiler contract is useful enough to justify client work.

## Client PoCs

### Milestone 6: Amp observer and navigator

**Entry condition:** Milestone 5 justifies an agent client.

**Question:** Can an agent request a bounded view and incrementally inspect evidence instead of ingesting the repository indiscriminately?

**PoC:** give Amp one pinned Tower question, inspect the bounded units and evidence it requests, and compare its answer with a session that uses ordinary repository tools.

Implementation:

- Load and follow Amp's skill-building guidance at implementation time.
- Create an Observer skill around stable CLI JSON commands.
- Return bounded units, typed relationships, omissions, and evidence handles.
- Add Navigator transformations only after Observer sessions establish a baseline.
- Record which units and evidence IDs the agent inspects without logging hidden reasoning.

Exit criteria:

- Amp can use Tower without Tower-specific instructions in the investigation prompt.
- The agent can request more detail without exceeding the declared budget silently.
- The same tasks are scored with and without Tower.

### Milestone 7: inspectable native UI

**Entry condition:** textual use identifies an interaction problem that a persistent UI could plausibly solve.

**Question:** Can a user inspect and navigate a saved Tower view more effectively in a persistent client without changing its semantics?

**PoC:** open a saved Tower-on-Tower Representation IR file in the native app, select each unit, inspect its evidence, and compare the displayed semantics with the terminal renderer.

Implementation:

- Build a minimal SwiftUI macOS client that loads saved Representation IR.
- Show the frame, units, typed connections, omissions, and evidence inspector.
- Preserve stable selection while switching among existing compiled views.
- Open exact source spans through an explicit user action.
- Keep presentation state separate from Representation IR.

Exit criteria:

- One saved view renders consistently in the terminal and native client.
- Every visible semantic element links to the same evidence in both clients.
- UI state cannot alter claims, relationship types, or provenance.
- Representative states pass visual and accessibility inspection.

### Milestone 8: strategic-map experiment

**Entry condition:** Milestone 7 identifies a concrete orientation or local-transformation problem that conventional panels do not solve well.

**Question:** Does spatial interaction improve focus continuity or comprehension over the inspectable native UI?

**PoC:** perform the same local refinement on one saved Tower view in conventional and spatial presentations, then compare focus continuity and answer correctness.

Implementation:

- Define one bounded spatial hypothesis and acceptance criteria before writing the viewport.
- Host an `MTKView` through SwiftUI and render one Tower-on-Tower representation with Metal.
- Implement only the camera, selection, local expansion, and viewpoint transition behavior required by that hypothesis.
- Keep semantic zoom tied to `Detail`; camera movement alone must not fabricate semantic detail.
- Store transforms and camera state in Scene IR, separate from Representation IR.
- Compare the spatial view with an orthographic or conventional presentation of the same representation.

Exit criteria:

- Spatial presentation consumes unchanged Representation IR.
- Selection and focus survive local expansion and viewpoint changes.
- Every spatial encoding has an explicit semantic legend and a precise inspectable alternative.
- Evaluation supports discarding, revising, or continuing the spatial approach.

An embedded terminal, `libghostty-vt`, PTY integration, revision-time terrain, and additional map modes are separate future experiments. None is a prerequisite for validating the compiler formula or the first graphical client.

## Later gates

AI-proposed interpretation, runtime traces, syntax-aware tooling, and testing on repositories other than Tower remain possible follow-up experiments. They are deliberately outside this plan until Tower-on-Tower demonstrates value and the `rg`/Git approach exposes a concrete limitation. When introduced, they must preserve the compiler contract: proposed facts remain distinguishable from evidence, all visible claims retain provenance, and client presentation never becomes semantic authority.
