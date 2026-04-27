# Findings Journal

This journal records live findings from Continuo implementation and testing.
It is intended to capture the gap between what the system can technically
retrieve and how naturally it behaves in the first moments of interaction.

---

## 2026-04-19 - Codex Recognition-First Gap

### Context
- Objective: test whether the Codex-specific Continuo integration produces
  recognition-first behavior, not just better retrieval.
- Systems: Codex adapter, `continuo codex eval --live`, live `~/.codex`
  ingestion, explicit `claude-brain` overlay ingest.
- Constraint: the first response needs to feel like human recognition while
  deeper context hydrates in parallel.

### Timeline
- Generic Codex Continuo integration was implemented, verified, committed, and
  pushed.
- Live eval against real Codex memory was tightened until project extraction
  became sane and obvious garbage entities were removed.
- Explicit ingest against `C:\Users\cumul\claude-brain` succeeded and pulled a
  large amount of real project context.
- User tested the behavior with a recognition-style question: `What do you know
  about OMNIvour?`
- Codex responded too much like a retrieval system: it searched first, then
  answered from gathered notes.
- User clarified the intended NeuroLayer/Continuo behavior:
  first-layer keyword recognition should support an immediate natural response,
  while deeper layers hydrate project summaries, dates, milestones, and archived
  history in the background.

### Decisions
- Decision: treat this as a real product finding, not user preference noise.
  Rationale: this behavior is central to the thesis and to the product promise.
  Impact: runtime behavior now becomes a first-class workstream, not just data
  ingestion quality.
- Decision: distinguish `data-layer success` from `behavior-layer success`.
  Rationale: Continuo can ingest and structure memory correctly while still
  feeling like lookup.
  Impact: future eval must score both context quality and response timing style.
- Decision: record recognition failures as journal artifacts.
  Rationale: these misses are high-value evidence for the thesis and the next
  implementation phase.
  Impact: this journal becomes the running record of cognition-timing findings.

### Actions
- Owner: Codex
  Action: create a recognition-first runtime path for Codex Continuo.
  Status: next
- Owner: Codex
  Action: add an L0 entity alias map so names like `OMNIVour`, `Prun`, and
  `Coolculator` resolve immediately to known project identities.
  Status: next
- Owner: Codex
  Action: add automatic L1 hydration so a recognized entity can immediately
  surface repo path, status, and key milestones without a visible lookup pause.
  Status: next
- Owner: Codex
  Action: add prompt-eval cases for recognition-first questions such as
  `What is OMNIVour?`, `What is Prun?`, and `Remind me what Coolculator is`.
  Status: next
- Owner: User + Codex
  Action: continue live conversational testing to pressure-test whether the
  first response moment feels natural.
  Status: active

### Open Questions
- What is the minimum L0 payload required for natural recognition without
  overstuffing the hot context?
- Should the first sentence be generated from a fixed recognition scaffold or a
  more flexible project-card format?
- How should runtime behavior decide when to stay at L1 versus descend into L2/L3
  archive retrieval?
- Should recognition-first eval be measured only by entity correctness, or also
  by response shape and latency?

### Working Answers
- L0 payload budget:
  target roughly 500 tokens, with an upper bound around 2000 tokens.
  This reflects the original design intuition that L0 must stay small enough to
  feel immediate while still carrying enough identity signal for recognition.
- First-response shape:
  prefer a flexible project-card format over a fixed recognition scaffold.
  The first sentence should still feel natural, but the underlying shape should
  support a compact identity + status + path + key-context payload rather than a
  rigid template.
- L1 versus L2/L3 descent:
  use a conditional runtime rule.
  If the system already has enough context to answer, answer with what it has.
  During that same window, continue looking up deeper context in parallel.
  Descend into archive/history only when the answer needs more support or the
  user asks for more depth.
- Recognition-first evaluation:
  measure both correctness and interaction quality.
  Entity correctness alone is not enough; evaluation should also score response
  shape and latency, because the thesis depends on the interaction feeling
  natural in the first moments.

### Risks
- The system may continue to optimize for retrieval quality while missing the
  human-interface timing problem the thesis is actually about.
  Note: this is the primary failure mode to watch, because it would let
  Continuo become a better database without becoming a more natural interface.
- Overfitting project extraction without a recognition runtime could create a
  stronger database that still feels clunky in use.
  Note: this is a good near-term warning sign for implementation work. Better
  entity extraction alone is not success if the first response moment still
  feels like lookup.
- Too much L0 context may improve recognition but degrade responsiveness or make
  the hot cache noisy.
  Note: this was a known pressure from the start, not a surprise regression. The
  open problem is to find the minimum hot context that still supports natural
  recognition.
- If recognition and hydration are not clearly separated, future debugging will
  blur data issues and runtime-behavior issues together.
  Note: this is likely a longer-term architecture concern. The system will need
  a stable boundary between `entity recognized`, `project summary hydrated`, and
  `archive descended` so future debugging can isolate data quality from runtime
  timing behavior.

### Refinements
- User refinement: the goal is not simply to reduce clunkiness in a general
  sense, but to make the first moments of human-AI interaction feel casual and
  natural enough that the interface stops feeling like staged call-and-response.
- User refinement: the recognition moment should buy time for deeper layers to
  arrive, in the same way human cognition often starts with recognition before
  details are consciously retrieved.
- User refinement: solving the `recognition vs hydration` boundary is part of
  the product architecture, not just implementation polish.

### Next Session Bootstrap
- Start with the recognition-first runtime path, not more adapter ingestion work.
- Use OMNIVour as the canonical test case for the first-response behavior.
- Use the current working defaults:
  L0 target around 500 tokens, cap around 2000;
  flexible project-card first response;
  conditional L1-to-L2/L3 descent;
  eval on correctness + response shape + latency.
- Preserve the distinction:
  `I know what this is` should happen first,
  `here are the deeper details` should arrive immediately after,
  `archive descent` should only happen when needed.
- Treat the target behavior as:
  recognition first,
  hydration second,
  archive third.

## 2026-04-22 - Role Narrative + Landscape Sweep

### Context
- Resumed Continuo work after a brief gap. Goal: review the project, sweep the
  agent-memory field for new findings, and formulate a small adoption plan.
- Picked the smallest plan item first: add `agent.role_narrative` to L5.

### Landscape findings (2026-04-22 sweep)
- Mature frameworks: Mem0 (3-tier scope, hybrid store, SOC 2), Zep (Graphiti,
  temporal validity windows), Letta (memory blocks, stateful runtime), Cognee
  (doc -> KG), Supermemory / SuperLocalMemory (local-first variants).
- Notable academic work:
  - Memora -- "primary abstractions + cue anchors" (Microsoft, Feb 2026,
    hf.co/papers/2602.03315). Structurally close to our L0/L1 split, framed
    as a representation problem rather than a runtime-timing problem.
  - Memory in the Age of AI Agents -- canonical 2025-2026 survey
    (hf.co/papers/2512.13564, 157 upvotes). Six memory types: token-level,
    parametric, latent, factual, experiential, working.
  - Enhancing MCP with Context-Aware Server Collaboration (arXiv 2601.11595)
    -- formalizes "Shared Context Store (SCS)" -- functionally our L6.
  - Intrinsic Memory Agents (hf.co/papers/2508.08997, Jan 2026) -- shows that
    role-aligned memory blocks reduce role drift in heterogeneous multi-agent
    systems. Directly inspired today's role_narrative feature.
- MCP 2026 roadmap -- transport scalability, agent communication, governance,
  enterprise readiness. SEP-1932 (DPoP) and SEP-1933 (Workload Identity
  Federation) sponsored. Our L6 stays roadmap-aligned without active work.
- No external product or paper found that frames the recognition-vs-retrieval
  *runtime timing* problem the way our 2026-04-19 entry does. White space
  remains.

### Decisions
- Decision: adopt role_narrative now, defer Memora-style abstraction/cue
  formalism to a later cycle.
  Rationale: role_narrative is one optional schema field with high
  differentiation payoff. Memora alignment is bigger surface and would
  require deeper read of the paper before commit.
  Impact: shipping role_narrative today, leaving abstraction/cue work as
  an open candidate for v0.1.x.
- Decision: do not rebuild as a knowledge graph (Cognee / Zep direction).
  Rationale: Continuo's wedge is timing, not representation richness.
  Adding graph engine = scope blowup with no thesis payoff.
- Decision: stay aligned with MCP 2026 roadmap on terminology + governance,
  but do not preemptively implement DPoP / Workload Identity Federation.
  Rationale: those are enterprise concerns; we are still pre-alpha.

### Actions
- Owner: Claude (today)
  Action: ship `agent.role_narrative` schema + dataclass + populations in
  Claude Code and Codex adapters + tests.
  Status: complete (commit 798836f)
- Owner: Claude (today)
  Action: populate role_narrative in Clyde native publisher.
  Status: next
- Owner: Future cycle
  Action: write spec/POSITIONING.md staking the recognition-first
  framing publicly before anyone else does.
  Status: open
- Owner: Future cycle
  Action: add Zep-style temporal validity windows (`valid_from` /
  `valid_to`) to L5 Entity.
  Status: open
- Owner: Future cycle
  Action: build the recognition-first runtime path
  (`core/recognition_runtime.py`) that emits an immediate recognition
  sentence while L1 hydrates in parallel.
  Status: open -- highest leverage item, deferred so we can warm up with
  smaller wins first.
- Owner: Future cycle
  Action: write spec/RELATED_WORK.md mapping our terms to Memora,
  Memory in the Age of AI Agents, SCS, G-Memory, H-MEM.
  Status: open

### Working Answers
- Role narratives differentiate within type slug: Claude Code = manager,
  Codex = lead author, Cursor = debugger, Cline = throwaway, Clyde =
  general-purpose. L6 query routing benefits immediately.
- Schema field is optional and capped at 500 chars; backwards-compatible
  with all existing manifests.

### Risks
- Recognition-first runtime work is still the headline gap. role_narrative
  is useful but does not by itself fix the lookup-feel problem. Watch for
  the trap of shipping many small wins while the central gap remains.
- Memora's framing is close enough to ours that aligning vocabulary later
  is cheap, but if a competing project picks up "abstraction + cue"
  vocabulary first, we look downstream of them.

### Next Session Bootstrap
- Either ship POSITIONING.md to stake recognition-first framing, or jump
  to recognition_runtime.py as the headline behavior fix.
- Temporal validity windows is the next-smallest concrete edit if a warm-up
  is preferred.
