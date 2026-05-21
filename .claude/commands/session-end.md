---
name: session-end
description: Close out a STRAT Scanner session with quality checks and documentation updates
---

# Session End Command

Execute the following steps in order. Pause for user confirmation where noted.

## Step 1: Run Pre-Commit Checks

Execute `/pre-commit` command (or perform these checks inline):

1. Check for changed files: `git status`
2. Check HANDOFF.md line count: should be < 1500 lines
3. Check if README.md reflects current system state (data provider, env vars,
   deployment status)
4. Check if CLAUDE.md has unnecessary bloat (should be < 250 lines for the
   scanner, which has a smaller surface area than ATLAS)

Report any issues found. If critical issues, STOP and ask user how to proceed.

## Step 2: Update Documentation

### Update `.session_startup_prompt.md`

Replace contents with template:
```markdown
# Session Startup Prompt - {Next Session Tag}

**Previous Session:** {tag} ({today's date})
**Current Branch:** `{branch}`
**Deployment:** {status from this session}
**Status:** {brief one-line state}

---

## Current Mission

{1-2 paragraphs}

---

## Mandatory Pre-Work Reading

1. `docs/HANDOFF.md`
2. `CLAUDE.md`
3. `docs/SCANNER_STATUS_BRIEF.md`

---

## Expected Environment Variables

{Update if any new vars were added or renamed}

---

## Reference

- `docs/HANDOFF.md`
- `docs/INDEX.md`
- Parent: `C:\Strat_Trading_Bot\CLAUDE.md`
```

### Update `docs/HANDOFF.md`

Add new session entry at TOP of file:
```markdown
## Session {tag}: {Brief Title} ({STATUS})

**Date:** {today's date}
**Branch:** {branch name}
**Status:** {COMPLETE / IN PROGRESS / BLOCKED}

### What Was Accomplished

{Detailed list of accomplishments}

### Files Modified

{List of files changed with brief description}

### Next Steps

{Concrete actions for the next session}

---
```

If HANDOFF.md exceeds 1500 lines after update:
- STOP and ask user: "HANDOFF.md is {X} lines. Archive older sessions?"
- If yes, move older sessions to `docs/archive/sessions/`

### Update `docs/SCANNER_STATUS_BRIEF.md`

If any of the following changed this session, refresh the brief:
- Deployment URL
- Data provider (Alpaca vs Tradier vs other)
- Last known healthy date
- Outstanding blockers

## Step 3: Prepare Commit

Generate conventional commit message based on changes:
- `feat:` for new features
- `fix:` for bug fixes
- `docs:` for documentation only
- `test:` for test additions
- `refactor:` for code restructuring
- `chore:` for scaffolding, tooling, dotfile changes

Show user:
```
PROPOSED COMMIT
===============
Message: {conventional commit message}

Files:
{git diff --stat output}

Proceed with commit? (y/n)
```

Wait for user confirmation before committing.

## Step 4: Output Session Summary

```
SESSION {tag} COMPLETE
======================

ACCOMPLISHED:
- {task 1}
- {task 2}

BLOCKERS: {none | list blockers}

NEXT SESSION PRIORITIES:
1. {priority 1}
2. {priority 2}

DEPLOYMENT NOTE:
- {whether this session changes warrant a redeploy}
- {whether the Tradier migration is unblocked, blocked, or unchanged}

Documentation updated. Ready for commit.
```

## Rules

- Do NOT commit without user confirmation
- Do NOT push to remote unless user explicitly asks
- Do NOT skip quality checks
- Do NOT archive HANDOFF.md without user confirmation
- Keep summaries concise but complete
