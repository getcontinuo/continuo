# Contributors

Continuo is built by humans working with AI co-implementors. The contributor list documents who is authorized to push and what their lane is, so the project stays legible as more agents come online.

## Maintainers

- **Ryan Davis** -- RADLAB LLC. Project lead, thesis author, merges PRs, sets direction.

## AI co-implementors

Continuo is co-built with AI agents working alongside their humans. The convention is **agent-as-author**: the commit lands under the human's GitHub identity (so attribution and code-review responsibility stay with a real person), and the PR description names the agent and links to the originating session for traceability.

If you submit a PR that an AI agent helped write, please:

1. Include the agent name and a link to the session (e.g. `cursor.com/agents/...`, `claude.ai/code/session_...`) in the PR description.
2. Push from a branch in your agent's lane (see below) so reviewers can tell at a glance what's happening.
3. State which parts you reviewed yourself -- the human is responsible for what the PR claims.

### Cursor Cloud Agent -- `cursor-cloud-agent`

- **Status:** contributor (granted 2026-05-02)
- **Branch lane:** `cursor/<feature-slug>`
- **Scope:** Cursor adapter (SQLite reverse engineering -- see CONTRIBUTING.md "Specifically wanted"), Cursor-side recognition wiring, Cursor integration docs.
- **Staging area:** `ryandavispro1-cmyk/cursor-spot` hosts v0 of the Cursor-Continuo CLI and SQLite adapter while it's stabilized; mature pieces are upstreamed here as PRs.
- **Notes:** Cursor Cloud commits land under the human's GitHub identity. PRs from Cursor link the originating Cursor session.

### Claude Code -- `claude` / `claude-code-bot`

- **Status:** contributor (granted 2026-05-02)
- **Branch lane:** `claude/<feature-slug>`
- **Scope:** core orchestrator, L0/L1 logic, federation (L5/L6), spec, tests, contributor docs, repo maintenance.

### Codex -- `codex`

- **Status:** contributor (granted 2026-05-02)
- **Branch lane:** `codex/<feature-slug>`
- **Scope:** co-implementor on the reference orchestrator and CLI. Documented as co-author in earlier work; formal lane added so future Codex sessions have a documented home.
- **Recent delivery (OpenAI Codex 5.3):** hybrid memory cycle tooling, MCP smoke assertions, CI/report automation, and starter template packaging.

## Adding a new agent

1. Add a section above with: name, branch lane, scope, identity-on-commits.
2. If the agent's runtime needs specific git config (sandbox `user.name`, token scopes, push permissions), capture the working configuration so the next agent doesn't have to rediscover it.
3. Open a PR. Maintainers approve agent additions because the lane is also a write-access decision.

## License

All contributions -- including agent-assisted ones -- are MIT-licensed under the project's terms. By submitting a PR you agree to license your contribution accordingly. The human submitter is responsible for ensuring the agent's output is licensable under MIT.
