"""
Continuo Memory Orchestrator -- Phase 1
=========================================
Tiered human-inspired memory for Clyde (Ollama + OpenAI Agents SDK)

Phase 1 scope:
  - L0: Hot cache -- always in system prompt
  - L1: Entity synopses -- triggered by L0 keyword detection, parallel loaded
  - L2: Stub only (wired in Phase 2 via UltraRAG async)

Author: Ryan Davis / RADLAB LLC
Date: 2026-04-14
"""

import os
import asyncio
import yaml
import time
from pathlib import Path
from typing import Optional

# -- CONFIG --------------------------------------------------------------------

BASE_DIR = Path(__file__).parent
L0_PATH  = BASE_DIR / "l0" / "hot_cache.yaml"
L1_DIR   = BASE_DIR / "l1"

# Token budget hard caps
L0_TOKEN_BUDGET = 3000
L1_TOKEN_BUDGET = 12000
L1_LOAD_TIMEOUT = 1.5   # seconds -- if L1 takes longer, proceed without it

# -- TOKEN ESTIMATOR -----------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return len(text) // 4

# -- L0: HOT CACHE -------------------------------------------------------------

def load_l0() -> tuple[str, list[str]]:
    """
    Load L0 hot cache from YAML.
    Returns: (formatted_context_string, list_of_entity_keywords)
    Always fast -- reads from disk, no inference.
    """
    with open(L0_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    identity = data.get("identity", {})
    projects = data.get("projects", [])
    hardware = data.get("hardware", {})
    focus    = data.get("current_focus", {})
    entities = data.get("entities", [])

    # Build compact L0 context string
    active_projects = [p["name"] for p in projects if p.get("priority", 9) <= 2]
    keywords = [e["keyword"] for e in entities]

    context = f"""## CLYDE MEMORY -- L0 CONTEXT
User: {identity.get('user')} ({identity.get('alias')}) | {identity.get('company')} | {identity.get('role')}
Active Projects: {', '.join(active_projects)}
Hardware: {hardware.get('local_model')} via {hardware.get('inference')}
Current Focus: {focus.get('primary')}
Last Session: {focus.get('last_session')} -- {focus.get('last_topic')}
Known Entities: {', '.join(keywords)}"""

    tokens = estimate_tokens(context)
    if tokens > L0_TOKEN_BUDGET:
        print(f"[Continuo] [WARN]L0 over budget: {tokens} tokens (max {L0_TOKEN_BUDGET})")

    return context, keywords

# -- L1: ENTITY SYNOPSES -------------------------------------------------------

def detect_entities(message: str, keywords: list[str]) -> list[str]:
    """
    Scan user message for L0 keyword hits.
    Returns list of matched entity names.
    Case-insensitive. O(n*m) -- fast enough for small L0 lists.
    """
    message_lower = message.lower()
    matched = []
    for kw in keywords:
        if kw.lower() in message_lower:
            matched.append(kw)
    return matched

def load_l1_synopsis(entity: str) -> Optional[str]:
    """Load a single L1 synopsis file. Returns None if not found."""
    # Try exact match first, then case-insensitive
    path = L1_DIR / f"{entity}.md"
    if not path.exists():
        # Try case-insensitive scan
        for f in L1_DIR.glob("*.md"):
            if f.stem.lower() == entity.lower():
                path = f
                break
        else:
            return None

    return path.read_text(encoding="utf-8")

async def load_l1_parallel(entities: list[str]) -> str:
    """
    Load L1 synopses for all detected entities in parallel.
    Respects token budget -- drops lowest-priority entities if exceeded.
    """
    if not entities:
        return ""

    # Load all in parallel using asyncio
    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, load_l1_synopsis, entity)
        for entity in entities
    ]
    results = await asyncio.gather(*tasks)

    # Build combined L1 context with token budget enforcement
    combined = "\n\n## CLYDE MEMORY -- L1 ENTITY CONTEXT\n"
    total_tokens = estimate_tokens(combined)

    for entity, synopsis in zip(entities, results):
        if synopsis is None:
            continue
        chunk = f"\n---\n{synopsis}"
        chunk_tokens = estimate_tokens(chunk)

        if total_tokens + chunk_tokens > L1_TOKEN_BUDGET:
            print(f"[Continuo] [WARN]L1 budget reached -- skipping: {entity}")
            break

        combined += chunk
        total_tokens += chunk_tokens

    return combined if total_tokens > estimate_tokens("\n\n## CLYDE MEMORY -- L1 ENTITY CONTEXT\n") else ""

# -- L2: Episodic Memory async retrieval --------------------------------------

async def query_l2_ultrarag(query: str, config=None) -> str:
    """
    L2 -- UltraRAG-backed async retrieval.

    Delegates to :func:`core.l2.query_l2` which reads config from the bundled
    YAML file (``core/l2_config.yaml``) plus any ``CONTINUO_L2_*`` env-var
    overrides. Returns an empty string when L2 is disabled (the default) or
    when the retriever is unreachable -- never raises, so this call can't
    crash a session.

    Parameters
    ----------
    query : str
        The user message or derived query.
    config : L2Config, optional
        Override the default config. When None, defaults load from YAML + env.
    """
    from core.l2 import query_l2  # lazy import to keep core.l2 optional

    return await query_l2(query, config=config)

# -- SYSTEM PROMPT BUILDER -----------------------------------------------------

def build_system_prompt(
    base_instructions: str,
    l0_context: str,
    l1_context: str = "",
    l2_context: str = ""
) -> str:
    """
    Assemble final system prompt in injection order:
    1. Base instructions
    2. L0 hot cache (always)
    3. L1 entity synopses (if loaded)
    4. L2 episodic context (if ready)
    """
    parts = [base_instructions.strip(), l0_context]
    if l1_context:
        parts.append(l1_context)
    if l2_context:
        parts.append(f"\n## CLYDE MEMORY -- L2 EPISODIC CONTEXT\n{l2_context}")
    return "\n\n".join(parts)

# -- MAIN ORCHESTRATOR ---------------------------------------------------------

class Continuo:
    """
    Phase 1 Memory Orchestrator for Clyde.

    Usage:
        memory = Continuo()
        system_prompt = await memory.prepare(
            user_message="let's work on Clyde today",
            base_instructions="You are Clyde, a local AI swarm assistant."
        )
        # Pass system_prompt to Ollama chat call
    """

    def __init__(self, l2_config=None):
        """
        Parameters
        ----------
        l2_config : L2Config, optional
            Configuration for the L2 layer. When None (default), L2 loads
            config from the bundled YAML + env-var overrides; since the
            bundled default is ``enabled: false``, L2 is a no-op unless the
            user has opted in.
        """
        self.l0_context, self.keywords = load_l0()
        self._l2_task: Optional[asyncio.Task] = None
        self._l2_result: str = ""
        self._l2_config = l2_config
        print(f"[Continuo] [OK] L0 loaded -- {len(self.keywords)} entities in hot cache")

    async def prepare(self, user_message: str, base_instructions: str) -> str:
        """
        Core timing orchestrator.

        Flow:
          1. L0 always present (already loaded at init)
          2. Detect entity hits in user message
          3. Fire L1 load + L2 query in parallel
          4. Wait for L1 (fast, 1.5s timeout)
          5. Return system prompt with L0 + L1
          6. L2 task continues running in background

        Returns: system prompt ready to inject into Ollama call
        """
        t_start = time.monotonic()

        # Detect which entities the user mentioned
        matched_entities = detect_entities(user_message, self.keywords)
        if matched_entities:
            print(f"[Continuo] [HIT] L0 hits: {matched_entities}")
        else:
            print(f"[Continuo] [MISS] No L0 hits -- using base context only")

        # Fire L1 + L2 in parallel
        l1_task = asyncio.create_task(load_l1_parallel(matched_entities))
        self._l2_task = asyncio.create_task(
            query_l2_ultrarag(user_message, self._l2_config)
        )

        # Wait for L1 with timeout (fast -- file reads)
        try:
            l1_context = await asyncio.wait_for(
                asyncio.shield(l1_task),
                timeout=L1_LOAD_TIMEOUT
            )
        except asyncio.TimeoutError:
            print(f"[Continuo] [WARN]L1 timeout -- proceeding with L0 only")
            l1_context = ""

        t_l1 = time.monotonic() - t_start
        print(f"[Continuo] [INFO] L1 ready in {t_l1:.3f}s -- "
              f"{estimate_tokens(l1_context)} tokens")

        # L2 keeps running in background
        # Access via self.get_l2_context() on next turn

        return build_system_prompt(base_instructions, self.l0_context, l1_context)

    async def get_l2_context(self) -> str:
        """
        Retrieve L2 context if ready.
        Call this before the SECOND model response to enrich with episodic memory.
        """
        if self._l2_task is None:
            return ""
        if not self._l2_task.done():
            print("[Continuo] [WAIT] L2 still loading -- skipping for this turn")
            return ""
        result = self._l2_task.result()
        self._l2_result = result
        return result

    def reload_l0(self):
        """Hot-reload L0 from disk without restarting. Call after editing hot_cache.yaml."""
        self.l0_context, self.keywords = load_l0()
        print(f"[Continuo] [RELOAD] L0 reloaded -- {len(self.keywords)} entities")

# -- CLI TEST ------------------------------------------------------------------

async def _test():
    """Quick smoke test -- run with: python orchestrator.py"""
    print("\n=== Continuo Phase 1 -- Smoke Test ===\n")

    memory = Continuo()

    base = "You are Clyde, Ryan's local AI assistant. Be direct, technical, and momentum-driven."

    test_messages = [
        "Let's work on Clyde today",
        "How is ILTT doing?",
        "What's the status of Continuo?",
        "What's the weather like?",  # No L0 hit -- should use base only
    ]

    for msg in test_messages:
        print(f"\n{'-'*50}")
        print(f"USER: {msg}")
        prompt = await memory.prepare(msg, base)
        token_count = estimate_tokens(prompt)
        print(f"SYSTEM PROMPT: {token_count} tokens")
        print(f"PREVIEW: {prompt[:200]}...")

if __name__ == "__main__":
    asyncio.run(_test())
