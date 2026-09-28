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
4. VCS explains changes but not the current system as a coherent whole.
5. Tests reveal important contracts, often only after the relevant test vocabulary/glossary is known.
6. Notes and diagrams in documentation provide interpretation but as they are not easy to manage to sync with code, they may no longer match the code.
7. As mentioned, AI would help but the person cannot easily see what was excluded or which statements are mis/interpretations.

The burden of maintaining the whole model remains in the person's working memory. More search results or a larger graph to represent the codebase can increase that burden rather than reduce it. The desired system must externalize the evolving mental model while allowing the person to challenge every part of it.

### 1.2 Example: A concrete Tower investigation

Consider the question:

> Where is Tower's search evidence defined, how did those files change, and which exact lines support the answer?

The answer is not located in one folder or represented by one relationship. One must connect:

- Documentation that describes search evidence.
- Source occurrences of the relevant command and terms.
- The files and source spans containing each occurrence.
- Commits and diffs that changed those files.
- Line provenance for the selected evidence.
- Candidate tests found by explicit names, without claiming a semantic test relationship.

`rg` can find the terms and Git can explain how the matching lines changed. `fzf` can narrow and preview candidates. However, none of these tools owns the bounded representation that emerges, records what it omitted, or preserves the same subject while one evidence region is refined.

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

The system that we call as "Tower" will be a **representation compiler for codebases**.

It will maintain typed, provenance-bearing evidence and compile that evidence into a representation appropriate to a question, focus, viewpoint, detail, and cognitive budget.

Tower starts as a proof of concept, not as a product implementation. The first goal is to learn whether a small representation compiler helps us investigate Tower itself as it is built. Architecture, performance, packaging, integrations, and a graphical shell are deliberately deferred until the CLI establishes that claim.

Hierarchy will appear as a side effect of operations such as abstraction, containment, and refinement. Hence, it is expected that it will not be the canonical storage model.

Conceptually:

```text
View = compile(Evidence, Question, Focus, Viewpoint, Detail, Budget)
```

This is the central contract, not illustrative notation:

- **Evidence** is the versioned set of facts and provenance the compiler may use.
- **Question** states the information need. During the deterministic PoC it consists of text, an explicit intent, and explicit search terms; unrestricted natural-language interpretation is not assumed.
- **Focus** anchors compilation to stable subjects in the evidence graph.
- **Viewpoint** chooses the relationship meanings and representation forms relevant to the question, such as topology, causality, ownership, or contract.
- **Detail** controls explanatory granularity, from summary through mechanism to source evidence. It is semantic refinement, not graphical magnification.
- **Budget** is a structured set of hard resource limits, such as maximum visible units and maximum included evidence bytes. The first PoC supports a visible-unit limit; later dimensions are added only when measured. Relevant material excluded by any limit is recorded as an omission.

The resulting **View** is Representation IR. It contains the complete input frame, visible units, typed connections, provenance, omissions, and transformation history; it is not a screen layout. Every supported input must have an observable and testable effect on compilation. Unsupported interpretation must remain explicit rather than being replaced by a plausible guess.

Compilation applies the inputs in a defined order:

1. Validate the evidence snapshot and resolve the focus to one or more stable subjects.
2. Convert the question's explicit intent and search terms into deterministic relevance criteria. Preserve its text as the human-readable information need.
3. Project the focused evidence through the relationship types allowed by the viewpoint.
4. Select abstractions or expansions appropriate to the requested detail.
5. Fit the candidates to the budget, preserving required context and recording excluded relevant candidates as omissions.
6. Materialize the view with its frame, provenance, diagnostics, and transformation history.

The dimensions constrain one another but do not take over one another's roles. The question determines what would be relevant; focus determines which subject the answer remains about; viewpoint determines how evidence is organized; detail determines the explanatory granularity; and budget determines how much of that explanation is visible. A budget must not alter factual status, a viewpoint must not create evidence, and detail must not mean screen scale. If the focus cannot be resolved or the evidence cannot support the question under the requested viewpoint, compilation produces a diagnostic View with no fabricated semantic units.

A representation in Tower must also be able to shift locally. For example, a topology of Tower may retain its CLI and evidence-store units while the search connection between them expands in place into a causal flow. The entire representation must not be forced into one global detail level or visual notation.

## 3. What would falsify the thesis

Tower is not successful merely because it produces attractive diagrams or plausible summaries. The claims about Tower should be considered unsupported if, on representative Tower-on-Tower investigations:

1. Users cannot answer behavioral questions more accurately than with classical IDE systems or with AI agents.
2. Generated groupings with the representation cannot explain why their members belong together.
3. Representations routinely hide conditions needed to predict behavior.
4. Moving between viewpoints causes the user to lose the original focus and to distract completely, leading to frustration.
5. Question, focus, viewpoint, detail, or budget are merely labels and do not predictably change the compiled view.
6. The implementation relies on hard-coded answers about Tower rather than generic evidence and compilation rules.
7. An AI agent gains no useful context control over its existing search and shell tools.

## 4. Tower principles

### 4.1 Evidence before interpretation

The initial deterministic collectors establish repositories, revisions, files, exact text matches, source spans, diffs, history, and line provenance through `rg` and Git. These tools do not establish calls, ownership, causality, or intent. Semantic relationships may be added later from another explicit evidence source or proposed by a human or AI, but must never be inferred merely because text matches or files changed together.

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

The Tower repository is the initial experimental corpus. Each executable slice is used to investigate the source and documentation added by earlier slices. This keeps every milestone locally runnable, exercises the tool during its own development, and lets the evidence model grow from observed needs rather than a speculative universal schema.

Self-hosting does not by itself establish that Tower generalizes to large, heterogeneous repositories. It is the bootstrap and product-discovery loop. Additional languages, runtime evidence, and external corpora become separate experiments only after Tower-on-Tower shows that the compiler contract is useful.

## 6. System architecture

```text
                              clients
                +----------------+----------------+
                |                |                |
           terminal text     Amp skill      native client
                +----------------+----------------+
                                 |
                   Representation IR / JSON files
                                 |
                     +-----------v------------+
                     | representation compiler |
                     | question, frame, rules  |
                     +-----------+------------+
                                 |
                     +-----------v------------+
                     | typed evidence snapshots|
                     | JSONL + source spans     |
                     +-----------+------------+
                                 |
                         +-------+-------+
                         |               |
                        rg              Git
```


## 7. Technology decisions

### 7.1 PoC implementation: Python

Use Python 3 for the first `tower` CLI because it minimizes implementation ceremony and makes representation rules and intermediate data easy to inspect and change. The PoC should be one package with straightforward modules, standard-library data structures, subprocess calls to existing tools, and tests. It should not introduce a plugin framework, daemon, async architecture, or distribution work before those are needed by an experiment.

Python orchestrates `rg` and Git and transforms their explicit output; it is not a source-analysis mechanism.

Python is a PoC choice, not the visual-client implementation language. If the textual experiments justify the strategic-map client, that client will be a native macOS application written in Swift, with SwiftUI for the application interface and Metal for the spatial viewport. The representation compiler remains a separate process with an inspectable protocol. Rewriting the compiler in Swift is a separate decision that requires measured constraints such as startup time, indexing throughput, memory use, deployment, or integration; choosing Swift for the client does not itself justify a rewrite.

### 7.2 Evidence storage: inspectable files first

Store Tower's entities, relationships, claims, provenance, and representations as versioned JSON or JSON Lines artifacts. Source text remains in the working tree; artifacts contain paths, revisions, source spans, hashes, and collector metadata.

Don't design a database schema during the PoC. Move to SQLite or another store only when artifact size, query behavior, or incremental updates create a measured problem. The JSON format is disposable and may evolve while the representation model is being learned.

### 7.3 Evidence collection

- Use `rg --files` for file discovery and `rg --json` for exact or regular-expression matches and context.
- Use read-only Git commands for revision identity, status, log, diff, changed files, and line provenance.
- Use optional `fzf` only to select and preview evidence for user themselves, by which it produces semantic facts.
- Recognize simple textual forms, such as Markdown headings, with explicit `rg` patterns rather than a parser.
- Preserve collector name, command parameters, and version on every derived fact.
- Add syntax-aware tooling only after an experiment records a concrete question that `rg` and Git cannot support.
- Suggest experiments if evidence at hand is not sufficient.

### 7.4 User interfaces

Interfaces arrive only after the backend behavior they consume is executable:

- **Milestone 5:** CLI, terminal output, JSON/JSON Lines, and optional `fzf` selection/preview.
- **Milestone 6:** an Amp skill tests bounded agent consumption of the same CLI contract.
- **Milestone 7:** a SwiftUI client tests persistent inspection of saved Representation IR.
- **Milestone 8:** only after a specific spatial question is identified, a Metal viewport tests strategic-map interaction.

### 7.5 Strategic-map client stack

If the textual and inspectable-UI experiments justify a strategic map, the native client will use:

- **Swift** for application state, input routing, Scene IR handling, layout, and orchestration.
- **SwiftUI** for the macOS application shell, commands, inspectors, controls, and accessibility integration.
- **MetalKit and Metal** for the interactive 2D/3D viewport, cameras, geometry, text surfaces, picking, and GPU rendering.

These components have deliberately narrow ownership. SwiftUI owns application-level composition and native controls; it hosts an `MTKView` through an AppKit representable only when rendering needs direct frame and input control. Metal owns the spatial drawing path. The representation compiler remains the source of semantic truth; the visual client consumes Representation IR and stores camera and presentation state separately as Scene IR.

The client will use Apple's native frameworks directly rather than introducing a game engine or cross-platform rendering abstraction. SwiftUI views must not own per-frame rendering state: a dedicated renderer object coordinates the `MTKView`, command queue, render passes, resource lifetimes, and Scene IR snapshots. AppKit interoperation should remain limited to capabilities that SwiftUI does not expose precisely enough, such as the Metal view and low-level keyboard or pointer handling.

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
- Display name.
- Content hash where applicable.
- Collector provenance.

PoC entity types:

- Repository, revision, working copy.
- Directory and file.
- Search query and source match.
- Commit/change and author identity.

#### Relationship

Required fields:

- Stable relationship ID.
- Typed source and target IDs.
- Direction.
- Source evidence spans.
- Derivation method.
- Confidence and status: observed, declared, statically derived, historically inferred, or AI-proposed.

PoC relationship types:

- Contains.
- Matched-by.
- Changed-in.
- Line-attributed-to.
- Changed-with, always marked as historical inference rather than semantic coupling.

Relationships such as declares, references, calls, mutates, owns, generates, implements, and precedes remain part of Tower's intended vocabulary, but they do not enter the PoC evidence graph until an explicit source can support them. A matching identifier is a source match, not a reference or call.

#### Claim

A claim is a statement intended for a representation. For example, “the `search` command normalizes every `rg` match into a source span” may be a human-authored claim supported by several matches; `rg` alone does not make it deterministic. Claims reference one or more entities and relationships, retain their complete evidence set, and remain visibly classified as deterministic, human-authored, or AI-proposed.

### 8.2 Representation IR

The Representation IR is separate from the evidence graph. It describes what is currently being explained and how its parts can be transformed.

Required concepts:

- **Subject:** the stable concept or evidence set being represented.
- **Frame:** the complete compilation request: question and intent, focus, viewpoint, detail, budget, and assumptions.
- **Unit:** a visible explanatory element backed by claims.
- **Typed connection:** a visible relationship with one explicit meaning.
- **Region:** a compositional scope that may use its own representation form.
- **Port:** a stable connection between a region and its surroundings.
- **Omission:** evidence intentionally hidden by compression.
- **Provenance:** links from every unit and connection to claims and evidence.
- **Transformation history:** rules that produced the current representation.

PoC representation forms:

- Repository/file topology.
- Change/history view.
- Evidence list and annotated source.

Later experiments may add functional decomposition, causal flow, decision trees, ownership, contracts, and timelines when their required semantic evidence exists. The IR must eventually support nested heterogeneous forms, but the PoC must first prove local transformations over repository, change, and evidence forms.

### 8.3 Representation transformations

Every transformation is a named, testable rewrite over the Representation IR.

Initial operations:

1. **Refine:** replace one unit with its supporting mechanism.
2. **Trace:** retain only elements connected through an explicit relationship type.
3. **Project:** hide irrelevant dimensions and record omissions.
4. **Collapse:** restore a transformed region to its boundary summary.

Abstract, reframe, reify relationship, contextualize, compare, and compose are later candidates. They should be added only when a PoC question requires them and the evidence model can preserve their semantics.

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

- Identify the current Git revision and working-copy state without mutating it.
- Pin experimental snapshots so results remain reproducible.
- Keep uncommitted changes distinguishable from indexed base content.

### R2. File and search evidence

- Enumerate searchable files through `rg --files` while honoring repository ignores.
- Execute exact and regular-expression searches through `rg --json`.
- Convert matches into normalized source spans.
- Stream search results to terminal, `fzf`, editor, and Amp clients.

### R3. Textual evidence

- Collect exact and regular-expression matches, context lines, and simple forms such as headings through explicit `rg` queries.
- Preserve the query that produced each match and never upgrade a match to a symbol reference, call, dependency, or cause.
- Use file paths and explicit naming patterns to find candidate tests, while labeling the result as textual evidence rather than a tests relationship.
- Update only files whose content hashes changed.

### R4. Git evidence

- Collect revision, dirty state, changed files, diff, history, author, and line provenance through read-only Git commands.
- Compute changed-with relationships over a configurable history window.
- Never assume that co-change proves semantic coupling; mark it as historical inference.
- Allow representation comparison between two revisions or working-copy states.

### R5. Evidence inspection

- Given any entity, relationship, or claim, print its complete provenance.
- Emit source locations that editors and clients can open at the exact span.
- Preview evidence in `fzf` without requiring an editor integration.
- Report stale evidence when file hashes no longer match.

### R6. Representation compilation

- Compile a representation according to `View = compile(Evidence, Question, Focus, Viewpoint, Detail, Budget)`.
- Store the complete compilation frame in the resulting Representation IR.
- Make every supported input operational: changing it must have a defined, testable effect or produce an explicit unsupported result.
- Use explicit question intent and search terms for deterministic relevance before unrestricted natural-language interpretation exists.
- Treat detail as semantic granularity and budget as structured hard limits. Initially implement only a maximum-visible-units limit.
- Record relevant excluded material as omissions when the budget or projection removes it.
- Support deterministic rule-only compilation before AI assistance is introduced.
- Permit local refinement. Defer local viewpoint changes until more than one evidence-backed semantic viewpoint exists.
- Save, reload, diff, and export Representation IR.
- Explain why each unit was included and why adjacent evidence was excluded.

### R7. Terminal and `fzf` workflow

- Search for a subject with `rg`-backed discovery.
- Select evidence or a saved representation through `fzf`.
- Preview source, provenance, and representation summaries.
- Run refine, project, trace, and collapse operations from selected items.
- Emit commands suitable for shell scripting rather than requiring an interactive UI.

### R8. Client protocol

- Treat Representation IR as the semantic boundary for terminal, agent, and graphical clients.
- Keep layout, camera, panels, and selection outside Representation IR.
- Require clients to preserve stable subject and unit IDs when switching presentation or requesting a transformation.
- Let clients open exact source spans without making the client the authority for evidence.
- Ensure the terminal renderer remains sufficient to inspect every semantic field exposed by a richer client.

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
- Let camera altitude request a different `Detail` value when appropriate; the compiler, not geometric scaling, decides which semantic units appear. Distant views may show territories and major routes while close views expose mechanisms and evidence.
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
- Support baseline sessions using ordinary `rg`, `fzf`, an editor, and Git without generated representations.
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
- Python 3, Git, `rg`, and `jq` are required initially; `fzf`, editor integrations, and Amp are optional capabilities.
- Paths and command invocation must support spaces and non-ASCII characters.
- The native clients in Milestones 7–8 target macOS and are not portability requirements for the representation compiler or textual clients.

### Testability

- Evidence collectors use fixture repositories.
- Transformation rules use golden Representation IR tests.
- Renderers test the same IR independently.
- Integration tests use temporary Git repositories.
- The native client uses serialized scene fixtures and screenshot tests for representative SwiftUI and Metal-rendered states.

## 11. Tool integration in practice

### 11.1 `rg`

Tower should invoke `rg --json` and preserve its match precision. It adds stable identities, source-span normalization, query provenance, and promotion of search results into representation evidence. It must not implement a slower substitute for textual search or relabel matches as semantic relationships.

### 11.2 `fzf`

Tower should emit tab-delimited or JSON-derived candidate streams with stable IDs. Preview commands retrieve source, provenance, or a compact representation. Selecting an item returns its stable ID to another Tower command, allowing shell composition.

Example target workflow:

```sh
tower search 'evidence' --format=fzf |
  fzf --preview 'tower evidence --preview {1}' |
  tower map --stdin \
    --evidence .tower/evidence.jsonl \
    --question 'Where is inspectable evidence defined?' \
    --intent locate-evidence \
    --term evidence \
    --viewpoint evidence \
    --detail evidence \
    --budget-units 7
```

The representation compiler CLI is now the stable contract for subsequent backend experiments.

### 11.3 Git

Tower invokes Git read-only and normalizes revisions, status, changes, diffs, history, and line provenance into evidence records. The PoC does not add a VCS abstraction before a second implementation is actually needed.

### 11.4 Amp skill

The skill evolves in three versions:

1. **Observer:** instruct Amp to query Tower status, search, and evidence while solving a task normally.
2. **Navigator:** allow Amp to compile, refine, project, and inspect representations.
3. **Evaluator:** compare an Amp investigation with and without Tower using fixed tasks, recorded actions, answer rubrics, and bounded context usage.

The skill must not tell Amp that Tower is helpful. It should explain the commands, decision rules, and limitations, then let evaluation determine usefulness.

## 12. Tower experimental corpus

Tower is its own initial corpus. Evaluation pins Tower revisions after executable backend slices exist so questions and expected answers remain reproducible while development continues.

### Task A: evidence lineage

> Where is the representation compiler contract defined, and which exact evidence supports each part of it?

This tests search evidence, normalized spans, provenance, and stale-evidence detection.

### Task B: bounded evidence trail

> Which Tower files and revisions define how search evidence is collected and inspected?

This tests whether question, focus, evidence/change viewpoints, detail, and a visible-unit budget produce a useful explanation from text matches and Git history without claiming unsupported program semantics.

### Task C: local representation change

> When one unit in an evidence view is refined or projected, what must remain stable and what new source or history evidence becomes visible?

This tests local rewrites, ports, focus continuity, omissions, and transformation history.

### Ground-truth package for each task

Before generating a representation, manually record:

- Correct explanatory claims.
- Necessary branch conditions and invariants.
- Supporting source and test spans.
- Distracting but irrelevant nearby code.
- Acceptable alternative explanations.
- A scoring rubric for submitted answers.

The compiler must not read the answer rubric. The rubric is evaluation data only.

## 13. Evaluation design

For each task, compare:

1. Existing tools only: an editor, `rg`, `fzf`, and Git.
2. Deterministic Tower.
3. Deterministic Tower with Amp as a client.
4. Tower with AI-proposed representations.
5. Native and strategic-map visualization, only when their entry conditions are met.

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

Use the same pinned Tower revision and avoid exposing ground-truth answers to the compiler, skill, or participants. Tower-specific answers must never be embedded in generic collectors or compilation rules.

## 14. Repository layout target

Create directories only as their milestone begins. The intended shape is:

```text
tower/                    small Python PoC package
  cli.py                  command-line interface
  evidence.py             evidence collection and provenance
  representation.py       Representation IR and rewrite rules
integrations/
  amp-skill/             Amp skill, added in Milestone 6
visualization/
  prototype/             Native macOS experiments, Milestones 7–8
experiments/
  formats/
  tower/
fixtures/                minimal evidence and representation corpora
docs/
  decisions/             short experiment and decision records
```

Do not create empty packages or integration shells before the milestone that uses them. Split the Python package only when its actual responsibilities make the split useful.

## 15. Decision on application form

The initial deliverable is a disposable proof of concept:

1. A small local Python CLI.
2. Inspectable JSON evidence and Representation IR artifacts.
3. Text output sufficient to run and score the selected Tower-on-Tower tasks.
4. Only the integrations needed to compare the PoC with the baseline workflow.

This is not yet a product architecture. Editor integration, an Amp skill, persistent storage, a service, packaging, and graphical clients are follow-up experiments. Each is added only when it answers a question that cannot be answered by the smaller CLI.

If the representation thesis is supported, the first visual experiment is a SwiftUI inspector for unchanged Representation IR. Metal is introduced only for a later, bounded spatial hypothesis. Product discovery can still revise the storage model, protocol, and boundaries from measured needs. The eventual product may feel more like a strategy game than a conventional developer application, but the CLI and compiler formula must earn that investment first.
