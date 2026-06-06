# QuantVault — Agent Instructions

Read `quantvault.md` before any code changes. It is the canonical spec.

Also read `docs/AI_CONTEXT.md`, `docs/HANDOFF.md`, `docs/CURRENT_TASK.md`, and `docs/ENGINEERING_LOG.md` at the start of every session.

## Financial Math Correctness

All financial calculations live in dedicated service files — never inline in routes.
Every calculation function must have a docstring explaining the formula and its financial interpretation.
Run unit tests verifying known values before marking any financial phase complete.

## GBrain Configuration (configured by /setup-gbrain)
- Mode: local-stdio
- Engine: pglite
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-06-05
- MCP registered: yes (user scope)
- Artifacts sync: off
- Current repo policy: read-write

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up and synced on this machine. Prefer gbrain over Grep for semantic questions.

- Semantic / "where is X handled?": `gbrain search "<terms>"` or `gbrain query "<question>"`
- Symbol lookup: `gbrain code-def <symbol>` or `gbrain code-refs <symbol>`
- Call graph: `gbrain code-callers <symbol>` / `gbrain code-callees <symbol>`
- Past decisions/plans: `gbrain search "<terms>" --source gstack-brain-keni`

Run `/sync-gbrain` to force-refresh after large code changes.

<!-- gstack-gbrain-search-guidance:end -->

## Skill Routing

- Architecture / phase review → `/plan-eng-review`
- Pre-ship code review → `/review`
- Post-feature QA → `/qa`
- Commits and push → `/ship`
- Financial math phases → run `/review` before marking complete (non-negotiable)
