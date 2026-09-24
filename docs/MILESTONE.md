## Milestones

Each milestone must end with executable behavior, tests, and a short decision record. While the PoC formats are experimental, later milestones may replace them rather than maintain migrations; they must not require speculative infrastructure in advance.

These milestones describe experiments, not a product roadmap. Until Milestone 3 is evaluated, prefer disposable code, inspectable artifacts, and the smallest implementation that can falsify the thesis. Product hardening begins only after a written continue/revise/stop decision.

### Milestone 0: experimental foundation

**Goal:** Make the research question falsifiable and reproducible.

Implementation:

- Initialize the repository and development tooling.
- Pin a Neovim revision and document how to prepare it (located in ~/projects/github.com/sand94/neovim/)
- Write ground-truth packages and scoring rubrics for Tasks A–C.
- Capture baseline investigations using Neovim, `rg`, `fzf`, and Git/Jujutsu.
- Define evaluation event and answer formats.
- Record baseline time, navigation count, files opened, and answer correctness.

Deliverables:

- `experiments/neovim/corpus.toml`
- `experiments/neovim/tasks/*.md`
- `experiments/schema/session.schema.json`
- Baseline session runner and redacted sample session

Exit criteria:

- Another person can reproduce the pinned corpus and run all three tasks.
- Each task has an independently reviewable answer rubric.
- The baseline toolchain is usable before Tower indexing exists.

### Milestone 1: local evidence spine

**Goal:** Establish stable repository identities and inspectable search evidence.

Implementation:

- Create a small Python package and `tower` CLI.
- Detect workspace root, Git/Jujutsu mode, revision, and dirty state.
- Write versioned JSON/JSON Lines evidence snapshots atomically.
- Ingest files through `rg --files` and content hashes.
- Wrap `rg --json`, normalize source spans, and stream JSON Lines.
- Implement `tower status`, `tower index`, `tower search`, and `tower evidence`.
- Add source preview and `fzf`-oriented output.

Exit criteria:

- Search results resolve to stable IDs and exact source spans.
- Editing one file invalidates only that file's indexed evidence.
- Git and Jujutsu fixture tests produce equivalent normalized workspace state.
- Baseline users can use Tower as a precise search/evidence wrapper without any AI.

### Milestone 2: typed evidence graph

**Goal:** Represent enough deterministic evidence for Task A.

Implementation:

- Add only the small C and Lua extractors needed by Task A; use Tree-sitter only where simpler extraction is unreliable.
- Index the symbols, declarations, syntax references, and selected call relationships required by the experiment.
- Parse relevant CMake target and generator relationships.
- Model generated-from lineage.
- Add Git/Jujutsu history and changed-with evidence.
- Implement entity, relationship, and claim inspection commands.
- Add deterministic test-to-API associations for Task A.

Exit criteria:

- Task A's required evidence can be retrieved without a repository-wide AI prompt.
- Generated API artifacts trace back to their authoring declarations and generators.
- Every relationship identifies its extractor and evidence spans.
- Unsupported relationships remain absent rather than guessed.

### Milestone 3: representation kernel

**Goal:** Test local representation shifts in the simplest useful textual form.

Implementation:

- Define version 1 of the Representation IR and JSON schema.
- Implement deterministic `refine`, `abstract`, `reify`, `trace`, `project`, `compose`, and `collapse` rules needed by Tasks A and B.
- Implement causal, ownership, contract, and evidence text renderers.
- Preserve ports and focus across local rewrites.
- Record omissions and transformation history.
- Add `tower map`, `tower refine`, `tower reframe`, `tower collapse`, and `tower explain`.
- Build golden tests from small fixtures before applying rules to Neovim.
- For one fixed Task B question and focus, produce candidate detail levels ranging from a signal or gist through a bounded 3–7-unit map, structured mechanism, and source evidence. Treat these levels as an experimental ladder, not as a fixed IR taxonomy or final UI control.
- Vary detail, visible-unit budget, and viewpoint independently. Observe whether users retain the subject, can predict what refinement will reveal, reach sufficient evidence without overload, and return to a compressed representation without losing necessary conditions.
- Run Task B with the baseline and textual PoC, then record a continue, revise, or stop decision using correctness, investigation effort, and evidence inspectability.

Exit criteria:

- One Task B representation combines an outer topology with an internally expanded causal region.
- Reframing that region as ownership preserves its subject and external ports.
- Every rendered unit resolves to deterministic evidence.
- Collapsing returns to a semantically equivalent boundary representation.
- The experiment records whether useful control over detail is best represented by discrete levels, a continuous budget, contextual selection, or no separate control, without adding scope beyond the question and focus.
- The comparison establishes whether representation operations add enough value to justify another milestone.

### Milestone 4: Neovim and interactive terminal workflow

**Goal:** Make representations usable during ordinary source investigation.

Implementation:

- Implement the Lua Neovim plugin as a thin asynchronous client.
- Add the commands listed in R8.
- Implement representation buffers, stable node selection, source jumps, and provenance views.
- Add `fzf` actions for mapping selected evidence and transforming saved representations.
- Add session instrumentation shared by terminal and Neovim clients.
- Run headless Neovim integration tests.

Exit criteria:

- A user can perform Task B entirely from Neovim, opening exact evidence as needed.
- Cancellation and stale-index handling work without blocking or corrupting buffers.
- The same saved Representation IR renders consistently in terminal and Neovim.

### Milestone 5: Amp observer and navigator skill

**Goal:** Determine whether an AI coding agent can consume the representation system incrementally.

Implementation:

- Load and follow Amp's skill-building guidance at implementation time.
- Create the Observer version of the Tower skill around stable CLI commands.
- Define bounded JSON response modes suitable for agent context windows.
- Add commands that bundle a unit with its typed relationships and selected evidence.
- Upgrade the skill to Navigator after Observer sessions establish a baseline.
- Log Tower actions and inspected evidence IDs without logging hidden reasoning.
- Run Tasks A–C in separate controlled Amp sessions with and without the skill.

Exit criteria:

- Amp can discover and use Tower without repository-specific instructions in the task prompt.
- Tower output remains bounded and Amp can request additional evidence deliberately.
- Answers are scored using the same rubric as human investigations.
- Results report correctness, tool actions, evidence inspected, elapsed time, and context volume where measurable.

### Milestone 6: AI proposal layer

**Goal:** Use AI to propose interpretations while preserving factual boundaries.

Implementation:

- Add the provider-neutral, capability-declaring `AiProposer` request/response schema.
- Implement the first provider adapter for TypeSafe Jev through the HTTP API, with credentials loaded from `TYPESAFE_API_KEY` and no credential persistence.
- Add a preview-first command that prints the endpoint, model, typed questions, selected evidence IDs/spans, and exact outbound excerpts; require an explicit send flag for the network request.
- Use Jev for closed-set evidence relation, labels, relationship types, candidate responsibilities/groupings, viewpoint changes, and missing-evidence judgments. Keep broader free-form proposal generation outside the Jev adapter.
- Validate all referenced IDs and source spans.
- Record complete Choice/Score distributions, Choice/Score confidence, and Noul probabilities without converting confidence into factual status.
- Render proposals distinctly from accepted and deterministic elements.
- Implement accept, reject, edit, and rationale capture.
- Store accepted proposals so representations can be replayed without the AI.
- Test proposal quality and calibration on withheld Neovim evidence, contradictory and insufficient evidence, ambiguous candidate sets, and adversarial nonexistent identifiers.
- Verify that missing credentials, network failure, rate limits, malformed responses, and provider disablement leave deterministic Tower operational.

Exit criteria:

- No invented entity or source span can enter an accepted representation unnoticed.
- A complete representation can distinguish deterministic, historical, human, and AI provenance.
- No repository content is sent without a visible manifest and explicit send action, and default logs contain no source excerpts or API keys.
- Jev outputs remain proposals until deterministic validation or a recorded human disposition accepts them.
- Jev improves at least one measured Task B or C outcome over deterministic Tower without reducing correctness.

### Milestone 7: strategic-map visualization experiment

**Entry condition:** Milestone 3 and subsequent textual workflows show that Tower improves at least one selected investigation, and the remaining evaluation identifies a spatial question that text cannot answer well.

**Goal:** Test whether a grand-strategy interaction model adds value without turning representations into decorative geography.

Implementation:

- Define the smallest visual hypothesis and acceptance criteria before implementing the client.
- Pin the Xcode and macOS deployment targets and a compatible Ghostty revision. Record licenses, required build tools, framework requirements, and supported macOS/CPU targets.
- Build a minimal SwiftUI macOS application that hosts an `MTKView` through an AppKit representable, and verify that it selects a Metal device and presents a rendered frame before building Tower UI code.
- Expose the public `libghostty-vt` C ABI through a Clang module, isolate it behind a typed Swift wrapper, and verify struct sizes, callbacks, ownership, and borrowed-data lifetimes against the pinned headers.
- Implement the PTY/process boundary in Swift: child output feeds `libghostty-vt`, encoded keyboard/mouse/paste/focus input returns to the PTY, and synchronous terminal effects are queued or handled without re-entering the terminal.
- Render a Ghostty render-state snapshot with Metal, including grapheme clusters, styles, cursor, selection, resize, and scrollback, rather than implementing a second terminal parser.
- Build one bounded Task B visual prototype with a world viewport, map-mode controls, contextual inspector, and evidence panel.
- Implement orbit, pan, tilt, perspective/orthographic switching, camera-altitude semantic zoom, stable selection, bookmarks, animated viewpoint transitions, and return-to-focus.
- Implement responsibility territories and volumes, typed borders, elevated causal/event routes, ownership and contract layers, change terrain/heat, and confidence/provenance overlays.
- Implement isolation, vertical slicing, exploded layers, transparency, cutaways, level-of-detail, and label decluttering.
- Implement nested heterogeneous regions, typed ports, local expansion, local reframing, evidence drawers, omissions, and provenance styling.
- Begin with explicit 3D layouts for topology, flow, ownership, and source evidence rather than one force-directed graph or universal terrain layout.
- Save semantic content as Representation IR and presentation/camera state as separate Scene IR.
- Add deterministic screenshots and serialized scene fixtures for visual regression tests.
- Link every source-backed element to Neovim through a local open command with explicit user action.

Exit criteria:

- A reproducible clean build produces a native macOS SwiftUI application using Metal and the pinned `libghostty-vt` artifact.
- A diagnostic reports the selected Metal device and active renderer; creating the viewport fails visibly if Metal is unavailable rather than silently selecting another renderer.
- The embedded terminal can run the Tower CLI through a PTY, survive resize, display representative Unicode and styled output, and route keyboard input and terminal-generated replies correctly.
- Task B can retain system context while its RPC edge expands into a causal mechanism and one queue unit reframes into ownership.
- Switching among causal, ownership, contract, change, and provenance map modes preserves the selected subject and recognizable landmarks.
- Changing camera altitude changes the represented information rather than merely scaling labels and geometry.
- Every use of elevation, depth, or volume has a visible semantic legend and can be flattened into a precise orthographic view.
- A user can select and inspect a deeply nested or initially occluded subject through isolation or cutaway controls.
- Moving the revision-time control updates changed regions without implying that co-change is causality.
- The visualization never uses an unlabeled generic relationship edge.
- Representative default and transformed states pass visual inspection and accessibility checks.
- Evaluation shows whether spatial interaction improves outcomes over the Neovim text representation.
- A written decision states whether to discard the prototype, iterate on it, or begin product design; the prototype itself is not treated as the product foundation.

Risk gates:

- Pin the minimum macOS version before relying on SwiftUI or Metal APIs introduced after that version; availability checks must not become an accidental second UI implementation.
- Keep SwiftUI state updates off the per-frame rendering path. If representable lifecycle or input bridging cannot satisfy the prototype's latency and control requirements, use a narrow AppKit host rather than adding a cross-platform engine.
- `libghostty-vt` promises neither source nor ABI stability. Upgrading the pinned revision requires rerunning ABI and terminal integration tests before visual work continues.
- Compile every Metal shader used by the prototype in clean and release builds, and test it on each supported Apple GPU family rather than inferring compatibility from the default scene.

### Milestone 8: generalization and runtime evidence

**Goal:** Determine whether the grammar generalizes beyond manually selected static cases.

Implementation:

- Complete Task C support without Neovim-specific hard-coded representation rules.
- Introduce an import format for optional runtime events and traces.
- Add observed temporal relationships without conflating them with all possible behavior.
- Test the same grammar on a second, smaller repository with different architecture.
- Profile indexing and representation queries before considering a persistent daemon.
- Decide whether a packaged desktop shell, language-server integration, or additional parsers are justified by evidence.

Exit criteria:

- Core rewrite rules work on the second corpus with configuration and extractors, not source-specific code.
- Static possibilities and observed runtime paths remain visibly distinct.
- A written evaluation supports continuing, revising, or rejecting the representation-compiler thesis.
