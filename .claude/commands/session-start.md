---
name: session-start
description: Automate STRAT Scanner development session startup sequence
---

# Session Start Command

Execute the following steps in order:

## Step 1: Read Session Context Files

Read these files and summarize key points:

1. `.session_startup_prompt.md` - Current session priorities
2. `docs/HANDOFF.md` - Recent session history (focus on last 2-3 sessions)
3. `CLAUDE.md` - Scanner development rules (STRICT COMPLIANCE)
4. `docs/SCANNER_STATUS_BRIEF.md` - Deployment health snapshot

## Step 2: Verify MCP Transport Health

The scanner is reached via MCP-over-SSE from the mobile Claude client. Note
in your output:

- Last known healthy date (from `SCANNER_STATUS_BRIEF.md`)
- Current data provider (Alpaca SIP today; Tradier post-migration)
- Whether the Tradier migration branch has landed yet

Do NOT actually probe the live server unless the user asks - that's a
debugging action, not a session-start action.

## Step 3: Output Session Brief

Format your output as:

```
SESSION STARTUP COMPLETE
========================

Project: STRAT Stock Scanner (Railway, MCP-over-SSE)
Branch: {current git branch}
Deployment: {healthy / broken / unknown - from SCANNER_STATUS_BRIEF}

TODAY'S PRIORITIES:
1. {from .session_startup_prompt.md}
2. {from .session_startup_prompt.md}
3. {from .session_startup_prompt.md}

RECENT CONTEXT:
- {Key point from HANDOFF.md latest session}
- {Key point about Tradier migration status if relevant}

REMINDERS:
- strat-methodology skill MANDATORY for ANY pattern detection work
- Scanner is NOT a trading system - read-only TFC reporting
- Do NOT touch Python source if working on a non-Python branch
- Accuracy over speed

Awaiting direction from user...
```

## Step 4: Wait for User Input

After outputting the brief, wait for the user to provide direction.

Do NOT start any development work until the user provides direction.

## Rules

- Do NOT skip any steps
- Do NOT summarize `CLAUDE.md` in full - just confirm it was read
- Do NOT start work without user direction
- Do NOT run the test suite at startup (use `/test-focus` when needed)
- Do NOT probe the live Railway endpoint unless asked
