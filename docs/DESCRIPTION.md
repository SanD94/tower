# Tower: A tool to look for an answer in anything

## 1. The question we started with

> How can a person understand a large, evolving codebase as a whole without being limited to VCS history or overwhelmed by its folder and file structure, by generating representations on demand that expose the right structure, behavior, boundaries, and evidence for the question currently being asked?

This is not primarily a request for another repository browser, dependency graph, UML generator, or AI summary. The problem is that a codebase has several simultaneously valid organizations, while conventional tools privilege only one:

- The filesystem privileges physical storage.
- VCS privileges change history.
- Call graphs privilege invocation.
- Language servers privilege symbols.
- Documentation privileges the organization its authors chose.
- AI chat privileges the context that happened to be retrieved.

None of these alone provides a mental model that can be well adjusted to a question at hand. The system must construct a purpose-specific representation from multiple kinds of evidence and allow that representation to change point of view without losing its subject or its connection to source code (the question).

### 1.1 What understanding a codebase feels like today

A person rarely begins with the name of the function they need. They begin with an incomplete question: “What is responsible for this?”, “Why does this happen later?”, “Who is allowed to change this state?”, or “What else will this change affect?” Existing tools require the person to translate that question into filenames, symbols, and search terms before those tools become useful.

The investigation then becomes a repeated loss and reconstruction of context:

1. A directory gives an initial location but not necessarily a responsibility.
2. Search produces occurrences without explaining which ones participate in the behavior.
3. Following calls reveals local mechanics while the larger purpose disappears from view.
4. VCS explains individual changes but not the current system as a coherent whole.
5. Tests reveal important contracts, often only after the relevant test vocabulary/glossary is known.
6. Notes and diagrams in documentation provide interpretation but as they are not easy to manage to sync with code, they may no longer match the code.
7. As mentioned, AI would help but the person cannot easily see what was excluded or which statements are mis/interpretations.

The burden of maintaining the whole model remains in the person's working memory. More search results or a larger graph to represent the codebase can increase that burden rather than reduce it. The desired system must externalize the evolving mental model while allowing the person to challenge every part of it.

### 1.2 Example: A concrete Neovim investigation

Consider the question:

> Why does one Neovim RPC request execute immediately while another enters the editor through `K_EVENT`?

The answer is not located in one folder or represented by one relationship. One must connect:

- RPC decoding and request handling.
- Generated handler metadata that classifies an API as fast or deferred.
- Different event queues and execution contexts.
- Admission into the editor state machine through `K_EVENT`.
- The safety restrictions and behavioral consequences of each path.
- Tests that establish the intended contract.

`rg` can find `K_EVENT`. Any editor with LSP can navigate symbols. `fzf` can narrow candidates. VCS can explain how relevant lines changed. An AI can help connect them. However, none of the tools owns the representation that emerges from the investigation.

The proposed solution is that there should be an inspectable, revisable representation which can allow different point of views for one to look at.

### 1.3 The experience we want

The representation should function as shared working memory between the person, editor, command-line tools, VCS, and AI. Source code remains the final evidence, but source layout no longer dictates the only way to understand it.

Its spatial interaction should resemble the information design of a layered-3D-map more than a diagram editor. The user inhabits one persistent 3D world, changes map modes to expose different truths, move from territories into local mechanisms, selects a subject to inspect it in depth, and moves through revision history without losing geographic orientation. Depth, elevation, layers, and volumes may express additional semantic dimensions when the active viewpoint defines them. All in all, this is an interaction reference, defined along the way for the question at hand.

### 1.4 Requirements visible before proposing an implementation

The human experience above already imposes several requirements:

- There cannot be one canonical hierarchy because the same code participates in structural, causal, ownership, contract, and historical organizations.
- “Zoom” cannot merely enlarge the same graph. More detail may require different entities, relationships, and visual forms.
- A representation shift must be local; one region may become a flow while its surroundings remain a topology.
- Relationships must state their meaning. “Calls,” “causes,” “mutates,” “owns,” and “changed with” are not interchangeable arrows.
- Abstraction must be reversible enough to reveal what was hidden and why.
- Every conclusion must retain a path to evidence and distinguish observed facts from intention, inference, or AI proposals.
- Existing tools must participate directly instead of being hidden behind a replacement environment.
- Hierarchy and levels should emerge from representation operations rather than constrain them in advance.

The implementation proposed below follows from these requirements.

## 2. Proposed solution: a representation compiler

The system that we call as "Tower" will be a **local-first representation compiler for codebases**.

It will maintain typed, provenance-bearing evidence and compile that evidence into a representation appropriate to a question, focus, viewpoint, and cognitive budget.

Tower starts as a proof of concept, not as a product implementation. The first goal is to learn whether a small representation compiler helps with the selected Neovim investigations. Architecture, performance, packaging, and a graphical shell are deliberately deferred until that claim has evidence behind it.

Hierarchy will appear as a side effect of operations such as abstraction, containment, and refinement. Hence, it is expected that it will not be the canonical storage model.

Conceptually:

```text
View = compile(Evidence, Question, Focus, Viewpoint, Detail, Budget)
```

A representation in Tower must be able to shift locally. For example, in neovim case, a system topology may retain its high-level client and editor nodes while the RPC edge between them expands in place into a causal flow. Similar to local spaces defined by nonlinear terms, the entire canvas must not be forced into one global level or one visual notation.

## 3. What would falsify the thesis

Tower is not successful merely because it produces attractive diagrams or plausible summaries. The claims about Tower should be considered unsupported if, on representative Neovim investigations:

1. Users cannot answer behavioral questions more accurately than with classical IDE systems or with AI agents.
2. Generated groupings with the representation cannot explain why their members belong together.
3. Representations routinely hide conditions needed to predict behavior.
4. Moving between viewpoints causes the user to lose the original focus and to distract completely, leading to frustration.
6. The implementation works only through hard-coded knowledge of a project at hand, i.e. Neovim above.
7. Any AI agent cannot use the system by the help of human with the aim to reduce the token usage. Its existing search and shell tools would solve the problem but what matters here is that the context should be narrowed down thanks to human becoming familiar with the codebase.

## 4. Tower principles

### 4.1 Evidence before interpretation

Deterministic extractors establish files, symbols, references, calls, generated-from relationships, changes, test associations, and runtime observations. AI may propose interpretations of that evidence, but it should be handled more rigorously.

### 4.2 Every visible claim is inspectable

For the representation in "Tower", every node, edge, label, grouping, omission, and ordering should expose:

- Its semantic type.
- Its supporting evidence.
- How it was derived.
- Its confidence, where inference was involved.
- What was omitted during compression (that's in question as filter costs as cognitive load).

### 4.3 Requirements

 - Different regions (questions) can use different viewpoints and detail levels at the same time. Expanding one relationship must not require transforming the whole representation.
 - An arrow to show relationship between nodes must never ambiguously mean “related to.” Relationships such as calls, causes, queues, mutates, owns, generates, implements, precedes, and usually-changes-with should remain distinct and it should depend on the local context.
 - Tower should orchestrate tools in a way that it defines a new type of utilization. A user must always be able to use generated representation along with ordinary source navigation.
 - The PoC should run as a small CLI with inspectable JSON input and output. If the thesis survives evaluation, later clients can share a stabilized protocol.

The long-term visualization hypothesis is that Tower could provide the strengths of layered-map interfaces: a navigable 3D world, persistent orientation, semantic zoom, selectable territories and volumes, map modes, overlays, an outliner, contextual inspectors, tooltips, and time controls. This is not a PoC requirement. It should be tested only after the textual representation proves useful. If tested, camera altitude, elevation, depth, and containment may carry meaning only when the active representation explicitly defines that meaning. The client must support orthographic, top-down, isolation, and cutaway views so 3D never prevents precise inspection.

## 5. Scope

The scope is very limited at the moment to see whether Tower will be working. To begin with, we need a repo for experimentation. For this reason, To apply representation grammar we define in Tower, we pick a pinned revision of `sand94/neovim` located in ~/projects/github.com/sand94/neovim/ for the following reasons:

- It includes C and Lua source, CMake generation rules, tests, and runtime files needed by the selected investigations.
- It has a lot of symbols to work on to understand how representations work.
- The problems in the repo require different viewpoints: causal, ownership, and contract/evidence.
- The layering system in Neovim does not depend on folder structure system, rather a convoluted relationship among different systems working together.


## 6. System architecture

```text
                                   clients
          +-----------+----------+----------+--------------------+
          |           |                     |                    |
       Neovim       Amp skill            terminal       strategic-map UI
          |           |                     |                    |
          +-----------+----------+----------+--------------------+
                                 |
                       experimental CLI / JSON files
                                 |
                     +-----------v------------+
                     | representation compiler |
                     | rules, views, rewrites  |
                     +-----------+------------+
                                 |
                     +-----------v------------+
                     | evidence snapshots      |
                     | JSON + source spans     |
                     +-----------+------------+
                                 |
          +-----------+----------+----------+-------------+
          |           |                     |             |
         rg       syntax indexers         git/jj       runtime traces
```


## 7. Technology decisions

### 7.1 PoC implementation: Python

Use Python 3 for the first `tower` CLI because it minimizes implementation ceremony and makes representation rules and intermediate data easy to inspect and change. The PoC should be one package with straightforward modules, standard-library data structures, subprocess calls to existing tools, and tests. It should not introduce a plugin framework, daemon, async architecture, or distribution work before those are needed by an experiment.

Python is a PoC choice, not a permanent product decision. Rust or another implementation language should be considered only if the PoC demonstrates value and measured constraints such as startup time, indexing throughput, memory use, deployment, or integration justify a rewrite.

### 7.2 Evidence storage: inspectable files first

Store the small, pinned experiment's entities, relationships, claims, provenance, and representations as versioned JSON or JSON Lines artifacts. Source text remains in the working tree; artifacts contain paths, revisions, source spans, hashes, and extractor metadata.

Don't design a database schema during the PoC. Move to SQLite or another store only when artifact size, query behavior, or incremental updates create a measured problem. The JSON format is disposable and may evolve while the representation model is being learned.

### 7.3 Parsing and search

- Use `rg --json` for exact-text discovery and streaming search results.
- Begin with `rg`, source spans, and small task-specific extractors. Add Tree-sitter for C or Lua only when a selected experiment needs syntax evidence that simpler extraction cannot provide reliably.
- Use build files and generator scripts as evidence; do not treat generated files as unrelated modules.
- Use language-server data later only where it adds relationships that the PoC cannot establish reliably.
- Preserve extractor name and version on every derived fact.

### 7.4 User interfaces

The interfaces are introduced here in order for one to understand how one can communicate with the system but it's detailed in Milestones (13) section.

- **Milestones 1–3:** terminal output, JSON, and optional `fzf` selection/preview.
- **Milestone 4:** a Lua Neovim plugin using asynchronous jobs and quickfix/location lists.
- **Milestone 7:** only after the textual PoC shows value, a bounded visual prototype tests whether a strategic-map interaction adds value.

## 8. Core domain model

### 8.1 Evidence graph

The evidence graph is where we define the relationship for the representation. It is not itself the user-facing representation.

#### Entity

Required fields:

- Stable entity ID.
- Entity type.
- Repository/workspace identity.
- Revision or working-copy identity.
- Source span where applicable.
- Display name and language.
- Content hash (?)
- Extractor provenance (?)

Initial entity types:

- Repository, revision, working copy.
- Directory and file.
- Build target and generated artifact.
- Module, type, function, method, field, and global.
- Test and fixture.
- API method and event.
- Queue, execution context, and state owner.
- Commit/change and author identity.

#### Relationship

Required fields:

- Stable relationship ID.
- Typed source and target IDs.
- Direction.
- Source evidence spans.
- Derivation method.
- Confidence and status: observed, declared, statically derived, historically inferred, or AI-proposed.

Initial relationship types:

- Contains and declares.
- Imports/includes and references.
- Calls.
- Reads and mutates.
- Enqueues and consumes.
- Generates and generated-from.
- Implements and tests.
- Precedes.
- Changed-with.

#### Claim

A claim is a statement intended for a representation, such as, in neovim case, “ordinary RPC requests execute through the editor event queue”, treated as a first class citizen in Tower. Claims reference one or more entities and relationships and retain their complete evidence set. Claims may be deterministic, human-authored, or AI-proposed. It can be tested accordingly.

### 8.2 Representation IR

The Representation IR is separate from the evidence graph. It describes what is currently being explained and how its parts can be transformed.

Required concepts:

- **Subject:** the stable concept or evidence set being represented.
- **Frame:** the current question, viewpoint, and assumptions.
- **Unit:** a visible explanatory element backed by claims.
- **Typed connection:** a visible relationship with one explicit meaning.
- **Region:** a compositional scope that may use its own representation form.
- **Port:** a stable connection between a region and its surroundings.
- **Omission:** evidence intentionally hidden by compression.
- **Provenance:** links from every unit and connection to claims and evidence.
- **Transformation history:** rules that produced the current representation.

Initial representation forms:

- Topology.
- Functional decomposition.
- Directed causal flow.
- Decision tree.
- State/ownership region.
- Contract provider/consumer view.
- Ordered timeline.
- Evidence list and annotated source.

The IR must support nested heterogeneous forms. For example, a topology edge may be replaced with a causal-flow region whose output port reconnects to the original destination.

### 8.3 Representation transformations

Every transformation is a named, testable rewrite over the Representation IR.

Initial operations:

1. **Refine:** replace one unit with its supporting mechanism.
2. **Abstract:** compress several units into one responsibility.
3. **Reframe:** preserve the subject while changing viewpoint.
4. **Reify relationship:** turn an edge into an inspectable region.
5. **Trace:** retain only elements participating in an outcome.
6. **Contextualize:** add surrounding dependencies without refining the subject.
7. **Compare:** align two paths, revisions, or implementations under one frame.
8. **Project:** hide irrelevant dimensions and record omissions.
9. **Compose:** place representations with different local forms in one scene.
10. **Collapse:** restore a transformed region to its boundary summary.

Each rule must declare:

- Accepted input pattern.
- Applicability conditions.
- Resulting units and connections.
- Port mapping from old to new representation.
- Claims preserved, added, and omitted.
- Required evidence.
- Whether the operation is deterministic or proposed.
- Recovery or inverse behavior.

### 8.4 Invariants

All clients and transformations must preserve:

1. **Provenance:** every visible claim resolves to source evidence.
2. **Type integrity:** relationship meaning never changes silently.
3. **Boundary compatibility:** local rewrites preserve valid external ports.
4. **Focus continuity:** the original subject remains identifiable.
5. **Explicit loss:** abstractions list meaningful omissions.
6. **Composability:** regions may differ in viewpoint and detail.
7. **Reproducibility:** deterministic inputs produce the same deterministic representation.
8. **Bounded complexity:** compilation accepts and respects a visible-unit budget.

## 9. Functional requirements

### R1. Workspace and revision identity

- Identify the current revision and working-copy state without mutating either VCS.
- Pin experimental snapshots so results remain reproducible.
- Keep uncommitted changes distinguishable from indexed base content.

### R2. File and search evidence

- Enumerate searchable files through `rg --files` while honoring repository ignores.
- Execute exact and regular-expression searches through `rg --json`.
- Convert matches into normalized source spans.
- Stream search results to terminal, `fzf`, Neovim, and Amp clients.

### R3. Structural and syntactic indexing

- Extract C and Lua symbols, declarations, definitions, and syntax-level references.
- Index relevant CMake targets and generator input/output relationships.
- Associate functional tests with referenced APIs and symbols using deterministic evidence.
- Update only files whose content hashes changed.

### R4. VCS evidence

- Provide equivalent read-only adapters for Git and Jujutsu concepts: revision, changed files, diff, history, author, and line provenance.
- Compute changed-with relationships over a configurable history window.
- Never assume that co-change proves semantic coupling; mark it as historical inference.
- Allow representation comparison between two revisions or working-copy states.

### R5. Evidence inspection

- Given any entity, relationship, or claim, print its complete provenance.
- Open source evidence in Neovim at the exact span.
- Preview evidence in `fzf` without requiring Neovim.
- Report stale evidence when file hashes no longer match.

### R6. Representation compilation

- Compile a representation from a question, focus, viewpoint, and unit budget.
- Support deterministic rule-only compilation before AI assistance is introduced.
- Permit local refinement and local viewpoint changes.
- Save, reload, diff, and export Representation IR.
- Explain why each unit was included and why adjacent evidence was excluded.

### R7. Terminal and `fzf` workflow

- Search for a subject with `rg`-backed discovery.
- Select evidence or a saved representation through `fzf`.
- Preview source, provenance, and representation summaries.
- Run refine, reframe, trace, and collapse operations from selected items.
- Emit commands suitable for shell scripting rather than requiring an interactive UI.

### R8. Neovim workflow

- Provide `:TowerSearch`, `:TowerMap`, `:TowerRefine`, `:TowerReframe`, `:TowerEvidence`, and `:TowerChanges` commands.
- Run Tower asynchronously and support cancellation.
- Use quickfix/location lists for source-backed collections.
- Open a representation in a dedicated buffer with stable node IDs and navigable links.
- Open exact source spans in ordinary windows.
- Preserve the user's current window and jump-list behavior.
- Initially render text and Unicode structures; launch or focus the strategic-map client only for representations that benefit from spatial interaction.

### R9. Amp integration

- Implement an Amp skill only after the basic CLI contract exists.
- The skill must teach Amp when to use Tower rather than replacing `rg` for simple exact searches.
- Expose commands for workspace status, subject discovery, map compilation, transformation, provenance inspection, and evaluation logging.
- Return bounded, structured output so Amp does not have to ingest the entire graph.
- Permit Amp to request more evidence incrementally.
- Record which representation units Amp inspected before producing an answer.
- Keep AI-produced claims in proposed state until validated by deterministic evidence or accepted by a human.

### R10. AI-assisted compilation

- Define a provider-neutral `AiProposer` interface; Amp is the first interactive AI client, not a hard-coded library dependency.
- Give AI a bounded evidence packet containing typed entities, relationships, source excerpts, the question, and budget.
- Ask AI for typed proposals conforming to a schema: labels, candidate responsibilities, candidate groupings, missing-evidence requests, or transformation choices.
- Validate referenced entity and relationship IDs.
- Reject invented source locations or unknown IDs.
- Store prompts, model/client identity when available, proposal output, validation result, and human disposition.
- Allow deterministic reruns without AI by loading previously accepted proposals.
- Never send repository content to an external model without an explicit client action and a visible evidence manifest.

### R11. Future visualization hypothesis (outside the initial PoC)

- Present the representation as a persistent 3D strategic world rather than a sequence of disconnected diagrams.
- Support orbit, pan, tilt, camera-altitude semantic zoom, selection history, bookmarks, and return-to-focus.
- Support perspective and orthographic cameras, including a top-down mode for precise comparison.
- Render responsibilities or other coherent groupings as selectable surfaces, territories, or volumes only when the active viewpoint provides evidence for those boundaries.
- Permit elevation, vertical layers, depth, and volume to encode one explicitly named semantic dimension at a time, such as abstraction depth, execution context, ownership containment, or change age. Never assign a permanent universal meaning to the vertical axis.
- Provide isolation, slicing, exploded, transparency, and cutaway controls for inspecting nested or occluded regions.
- Preserve recognizable landmarks and selection across map-mode changes wherever the underlying subjects remain the same.
- Provide map modes for responsibility, causality, ownership, contracts, change/history, and confidence/provenance; each mode defines its own borders, overlays, routes, labels, and available actions.
- Let camera altitude change representation grammar: distant views show territories, volumes, and major routes; intermediate views show mechanisms and interfaces; close views expose operations and source evidence.
- Render heterogeneous nested regions rather than forcing one graph layout. A selected volume may contain a flow, state machine, timeline, layered structure, or source panel.
- Provide an outliner, command/search palette, contextual inspector, hover tooltips, legend, and revision-time control around the map.
- Render typed calls, events, queue transfers, or observed runtime flow as unambiguous 3D routes whose direction remains readable from supported camera angles. Motion must communicate state rather than decorate it.
- Use level-of-detail, label decluttering, depth cues, selection outlines, and focus dimming to prevent the third dimension from increasing cognitive load.
- Visually distinguish factual, inferred, human-authored, and AI-proposed elements.
- Display typed edges and provide a legend scoped to the current scene.
- Expand and collapse regions without losing surrounding context.
- Reframe one region independently from its neighbors.
- Provide a persistent path from every visual unit to evidence.
- Display omissions and confidence without overwhelming the default view.
- Support keyboard-first navigation.
- Store presentation state in a versioned Scene IR separate from semantic Representation IR. Scene IR contains 3D transforms, camera transform and projection, spatial placement, active vertical-axis meaning, map mode, cutaway/layer state, open panels, selection, and visual overrides but cannot alter semantic claims.
- Export a static representation for review and testing.

### R12. Feedback and correction

- Let users rename a proposed unit, reject a grouping, correct an edge type, and attach rationale.
- Store corrections separately from extracted evidence.
- Reapply compatible corrections after reindexing.
- Surface conflicts when source changes invalidate a correction.
- Treat corrections as evaluation data, not automatically as universal rules.

### R13. Evaluation instrumentation

- Record task start/end, queries, transformations, evidence opened, and answers submitted.
- Support baseline sessions using ordinary `rg`, `fzf`, Neovim, and Git/Jujutsu without generated representations.
- Support Tower-assisted sessions for the same pinned revision and task.
- Keep self-reported usefulness separate from correctness and navigation measurements.
- Export anonymizable session data as JSON.

## 10. Non-functional requirements

### Performance

- Record startup, extraction, and representation-generation time for each experiment.
- Keep feedback fast enough for repeated investigation, but do not optimize against invented product budgets.
- If performance interrupts the experiment, profile before adding caches, a database, concurrency, or a lower-level implementation.

Product-level performance targets should be set from observed PoC usage.

### Safety and privacy

- All indexing and deterministic compilation run locally.
- Read-only commands must not mutate the repository, VCS, or editor buffers.
- AI evidence packets are explicit and inspectable.
- Logs must avoid source contents by default; store entity IDs and spans unless evaluation explicitly requires excerpts.

### Reliability

- PoC commands write artifacts atomically so an interrupted run does not replace the last complete result.
- Artifact and Representation IR versions are explicit, but compatibility migrations are not required while the PoC format remains experimental.
- A stale working copy must produce a warning rather than silently displaying invalid spans.

### Portability

- The PoC supports the development environment first and avoids unnecessary platform-specific APIs.
- Python 3, Git, and `rg` are required external tools initially; `fzf`, Jujutsu, Neovim, and Amp integrations are optional capabilities.
- Paths and command invocation must support spaces and non-ASCII characters.

### Testability

- Extractors use fixture repositories.
- Transformation rules use golden Representation IR tests.
- Renderers test the same IR independently.
- Integration tests use temporary Git and Jujutsu repositories.
- Neovim tests run headlessly.

## 11. Tool integration in practice

### 11.1 `rg`

Tower should invoke `rg --json` and preserve its match precision. It adds stable identities, source-span normalization, relation to indexed symbols, and promotion of search results into representation evidence. It must not implement a slower substitute for textual search.

### 11.2 `fzf`

Tower should emit tab-delimited or JSON-derived candidate streams with stable IDs. Preview commands retrieve source, provenance, or a compact representation. Selecting an item returns its stable ID to another Tower command, allowing shell composition.

Example target workflow:

```sh
tower search 'handle_request' --format=fzf |
  fzf --preview 'tower evidence --preview {1}' |
  tower map --stdin --viewpoint causal
```

The exact CLI may change before Milestone 2 freezes it.

### 11.3 Git and Jujutsu

Define a `VcsAdapter` contract around concepts rather than command output formats. Git and Jujutsu adapters normalize revisions, changes, diffs, and history into the same evidence schema. Colocated repositories should prefer the user's detected working-copy system while retaining Git object identity when useful.

### 11.4 Amp skill

The skill evolves in three versions:

1. **Observer:** instruct Amp to query Tower status, search, and evidence while solving a task normally.
2. **Navigator:** allow Amp to compile, refine, reframe, and inspect representations.
3. **Evaluator:** compare an Amp investigation with and without Tower using fixed tasks, recorded actions, answer rubrics, and bounded context usage.

The skill must not tell Amp that Tower is helpful. It should explain the commands, decision rules, and limitations, then let evaluation determine usefulness.

## 12. Neovim experimental corpus

Pin one Neovim commit before collecting baselines. Store the repository URL, commit, required build/generated-artifact instructions, and corpus hash in `experiments/neovim/corpus.toml`.

### Task A: localized contract

> Why does `nvim_buf_line_count()` behave differently for unloaded buffers, and which contract and tests would need review before changing it?

This tests contract lineage, state evidence, generated API metadata, and test discovery without requiring a large flow.

### Task B: cross-cutting mechanism

> Why does an RPC request sometimes execute immediately while another request enters the editor through `K_EVENT`?

The expected representation must connect request decoding, handler metadata, fast/deferred admission, event queues, the editor state machine, execution-context restrictions, and tests.

This is the primary design task because it is bounded but cannot be represented adequately by folders or an untyped call graph.

### Task C: distributed lifecycle

> When a built-in TUI disconnects, under which conditions does Neovim detach the UI, reconnect, or exit?

This tests lifecycle branches, distributed ownership, deferred cleanup, client/server topology, and evidence spread across physical subsystems.

### Ground-truth package for each task

Before generating a representation, manually record:

- Correct explanatory claims.
- Necessary branch conditions and invariants.
- Supporting source and test spans.
- Distracting but irrelevant nearby code.
- Acceptable alternative explanations.
- A scoring rubric for submitted answers.

The generator must not read the answer rubric. The rubric is evaluation data only.

## 13. Evaluation design

For each task, compare:

1. Existing tools only: Neovim, `rg`, `fzf`, and Git/Jujutsu.
2. Deterministic Tower.
3. Deterministic Tower with Amp as a client.
4. Tower with AI-proposed representations.
5. Strategic-map visualization, when available.

Within the strategic-map condition, compare the full 3D perspective mode with its orthographic top-down mode. The third dimension must improve orientation, relationship comprehension, or retention rather than merely increase visual novelty.

Measure:

- Answer correctness against the rubric.
- Time to first correct explanation.
- Files and source spans opened.
- Search and navigation operations.
- Incorrect claims and omitted branch conditions.
- Ability to predict a related unfamiliar behavior.
- Confidence calibration.
- Delayed reconstruction of the mental model.
- Human corrections required.
- For Amp, context volume and tool calls where observable.

Use the same pinned revision and avoid exposing ground-truth answers to the generator, skill, or participants.

## 14. Repository layout target

Create directories only as their milestone begins. The intended shape is:

```text
tower/                    small Python PoC package
  cli.py                  command-line interface
  evidence.py             evidence collection and provenance
  representation.py       Representation IR and rewrite rules
integrations/
  nvim/                  Lua plugin, added in Milestone 4
  amp-skill/             Amp skill, added in Milestone 5
visualization/
  prototype/             optional visual experiment, Milestone 7
experiments/
  formats/
  neovim/
fixtures/                minimal extractor and representation corpora
docs/
  decisions/             short experiment and decision records
```

Do not create empty packages or integration shells before the milestone that uses them. Split the Python package only when its actual responsibilities make the split useful.

## 15. Decision on application form

The initial deliverable is a disposable proof of concept:

1. A small local Python CLI.
2. Inspectable JSON evidence and Representation IR artifacts.
3. Text output sufficient to run and score the selected Neovim tasks.
4. Only the integrations needed to compare the PoC with the baseline workflow.

This is not yet a product architecture. Neovim integration, an Amp skill, persistent storage, a service, packaging, and a strategic-map client are follow-up experiments. Each is added only when it answers a question that cannot be answered by the smaller CLI.

If the representation thesis is supported, product discovery can choose an implementation language, storage model, protocol, and UI from measured needs. The eventual product may still feel more like a strategy game than a conventional developer application, but the PoC must earn that investment first.
