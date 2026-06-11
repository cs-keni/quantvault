# QuantVault — Agent Instructions

Read `docs/quantvault.md` before any code changes. It is the canonical spec.

Also read `docs/AI_CONTEXT.md`, `docs/HANDOFF.md`, `docs/CURRENT_TASK.md`, and `docs/ENGINEERING_LOG.md` at the start of every session.

## Financial Math Correctness

All financial calculations live in dedicated service files — never inline in routes.
Every calculation function must have a docstring explaining the formula and its financial interpretation.
Run unit tests verifying known values before marking any financial phase complete.

## GBrain Configuration (configured by /setup-gbrain)
- Mode: local-stdio
- Engine: postgres (Supabase)
- Config file: ~/.gbrain/config.json (mode 0600)
- Setup date: 2026-06-05
- MCP registered: yes (user scope)
- Artifacts sync: off
- Current repo policy: read-write

## GBrain Search Guidance (configured by /sync-gbrain)
<!-- gstack-gbrain-search-guidance:start -->

GBrain is set up and synced on this machine. The agent should prefer gbrain
over Grep when the question is semantic or when you don't know the exact
identifier yet.

**This worktree is pinned to a worktree-scoped code source** via the
`.gbrain-source` file in the repo root (kubectl-style context). Any
`gbrain code-def`, `code-refs`, `code-callers`, `code-callees`, or `query`
call from anywhere under this worktree routes to that source by default —
no `--source` flag needed. Conductor sibling worktrees of the same repo
each have their own pin and their own indexed pages, so semantic results
match the actual code on disk in this worktree.

Two indexed corpora available via the `gbrain` CLI:
- This worktree's code (auto-pinned via `.gbrain-source`).
- `~/.gstack/` curated memory (registered as `gstack-brain-keni` source via
  the existing federation pipeline).

Prefer gbrain when:
- "Where is X handled?" / semantic intent, no exact string yet:
    `gbrain search "<terms>"` or `gbrain query "<question>"`
- "Where is symbol Y defined?" / symbol-based code questions:
    `gbrain code-def <symbol>` or `gbrain code-refs <symbol>`
- "What calls Y?" / "What does Y depend on?":
    `gbrain code-callers <symbol>` / `gbrain code-callees <symbol>`
- "What did we decide last time?" / past plans, retros, learnings:
    `gbrain search "<terms>" --source gstack-brain-keni`

Grep is still right for known exact strings, regex, multiline patterns, and
file globs. Run `/sync-gbrain` after meaningful code changes; for ongoing
auto-sync across all worktrees, run `gbrain autopilot --install` once per
machine — gbrain's daemon handles incremental refresh on a schedule.

Safety: don't run `/sync-gbrain` while `gbrain autopilot` is active — the
orchestrator refuses destructive source ops when it detects a running autopilot
to avoid racing it (#1734). Prefer registering user repos with `gbrain sources
add --path <dir>` (no `--url`): URL-managed sources can auto-reclone, and the
sync code walk for them requires an explicit `--allow-reclone` opt-in.

<!-- gstack-gbrain-search-guidance:end -->

## Skill Routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

- Architecture / phase review → `/plan-eng-review`
- Pre-ship code review → `/review`
- Post-feature QA → `/qa`
- Commits and push → `/ship`
- Financial math phases → run `/review` before marking complete (non-negotiable)
- Strategy/scope → `/plan-ceo-review`
- Design system/plan review → `/design-consultation` or `/plan-design-review`
- Full review pipeline → `/autoplan`
- Bugs/errors → `/investigate`
- Visual polish → `/design-review`
- Ship/deploy/PR → `/land-and-deploy`
- Save/resume progress → `/context-save` / `/context-restore`
- Author a backlog-ready spec/issue → `/spec`

## Architecture Decisions (locked 2026-06-05 via /plan-eng-review)

See `docs/PHASES.md` for the full decision log. Key overrides from the spec:

- PyJWT (not python-jose) — active CVEs in python-jose
- VaR annual = rolling 252-day window, NOT `daily_var * sqrt(252)`
- Monte Carlo: `standard_t(df=5)` scaled to `daily_sigma`
- MC contributions: inject at year boundary, compound forward (not add-to-all cumprod)
- CVaR: `var_index = max(int((1 - confidence) * N), 1)` — prevents empty slice NaN
- Efficient frontier: solve min-variance first; use its return as the lower target bound
- Beta: `_compute_beta()` + `calculate_beta_from_ticker()` + `calculate_beta_from_returns()`
- Celery + Redis for CPU-bound tasks (efficient frontier, Monte Carlo, backtest)
- `ProcessPoolExecutor.map()` for the 100 scipy.optimize.minimize calls
- `User.default_portfolio_id FK` (not `Portfolio.is_default bool`)
- `portfolio_to_weights(holdings) -> tuple[list[str], np.ndarray]` in portfolio_service.py
