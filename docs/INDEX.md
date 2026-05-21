# Documentation Index - STRAT Stock Scanner

Quick map of what lives where in this repo's documentation.

## Tier 1 (read every session)

| File | Purpose |
|------|---------|
| `../CLAUDE.md` | Scanner-specific development rules |
| `../HANDOFF.md` | Session history, recent decisions, current state |
| `../.session_startup_prompt.md` | Today's mission and priorities |

## Tier 2 (operational)

| File | Purpose |
|------|---------|
| `SCANNER_STATUS_BRIEF.md` | One-page deployment-and-health snapshot |
| `DEPLOYMENT.md` | Railway deployment guide |
| `../README.md` | Public-facing feature catalog |

## Tier 3 (project-internal, gitignored locally)

| File | Purpose |
|------|---------|
| `../IMPLEMENTATION_SUMMARY.md` | Implementation notes (internal) |
| `../CLAUDE_WEB_IMPLEMENTATION_BRIEF.md` | Web client integration brief (internal) |
| `../DEBUGGING_SESSION_SUMMARY.md` | Past debugging session summary (internal) |
| `claude.md` | Local Claude scratchpad (gitignored) |

## Parent / Spine Documents

| File | Purpose |
|------|---------|
| `C:\Strat_Trading_Bot\CLAUDE.md` | Universal cross-project safety rules |
| `C:\Strat_Trading_Bot\vectorbt-workspace\docs\HANDOFF.md` | ATLAS history (source of methodology truth) |

## Adding New Documentation

- Keep `HANDOFF.md` under 1500 lines. Archive older entries to
  `docs/archive/sessions/` when the file outgrows that.
- New operational guides go in `docs/` and get listed in this index.
- Do NOT create `SESSION_XX_*.md` files - use `HANDOFF.md` only.
- Do NOT create internal docs at the repo root - put them in `docs/`
  and add to the gitignore if they contain sensitive content.
