---
name: pre-commit
description: Run quality checks before committing scanner code
---

# Pre-Commit Quality Checks

Execute all checks and report results. Do NOT auto-fix issues - report them
for user decision.

Note: Test suite is NOT run here (use `/test-focus` if you need to verify
tests before committing).

## Check 1: Changed Files Review

```bash
git diff --name-only
git diff --stat
```

For each changed file, flag:
- Python source under repo root (e.g., `server.py`, `strat_detector.py`,
  `alpaca_client.py`, `mcp_tools.py`) - methodology / transport review
- Auth/security files (`auth_server.py`, `auth_middleware.py`,
  `rate_limiter.py`) - security review
- `requirements.txt`, `railway.json`, `Dockerfile` - deployment review
- `.env*` - SECRET LEAK CHECK (block commit if `.env` itself was modified)

Status: {X files changed, Y need review}

## Check 2: Secrets and Credentials Scan

Scan staged content for likely-secret patterns:

- `ALPACA_API_KEY=`
- `ALPACA_SECRET_KEY=`
- `TRADIER_TOKEN=`
- `JWT_SECRET=`
- Long base64-looking strings in committed files
- Hardcoded VPS or server IPs

If any are found, STOP and report. Do not proceed to commit.

Status: PASS / SECRETS DETECTED

## Check 3: STRAT Methodology Review (if applicable)

If any of these files changed:
- `strat_detector.py`
- `mcp_tools.py` (for TFC scoring or pattern wiring)

Confirm:
- `strat-methodology` skill was invoked this session
- Bar classification uses 2U/2D, never bare "2"
- Entry timing logic does NOT wait for bar close
- TFC scoring matches the documented 0-5 scale

Status: PASS / NEEDS METHODOLOGY REVIEW

## Check 4: HANDOFF.md Size

```bash
wc -l docs/HANDOFF.md
```

- If < 1500 lines: PASS
- If >= 1500 lines: NEEDS ARCHIVE

Status: {X lines} - PASS / NEEDS ARCHIVE

## Check 5: README.md Accuracy

Compare README.md claims against actual system:
- Is the listed data provider current (Alpaca vs Tradier)?
- Are listed MCP tools actually registered in `mcp_tools.py`?
- Are version numbers and env-var requirements current?
- Are any deprecated features still listed?

Status: PASS / NEEDS UPDATE (list issues)

## Check 6: CLAUDE.md Health

Check `CLAUDE.md` for:
- Duplicate rules
- ATLAS-only rules that crept back in (VBT 5-step, ThetaData, dashboard,
  backtesting validation)
- Outdated references (e.g., stale data provider, retired endpoints)
- Excessive length (should be < 250 lines for token efficiency)

Status: PASS / NEEDS CLEANUP (list issues)

## Summary Output

```
PRE-COMMIT CHECK RESULTS
========================

[PASS/FAIL] Changed Files: X files, Y flagged for review
[PASS/FAIL] Secrets Scan: {status}
[PASS/SKIP] STRAT Methodology: {status}
[PASS/WARN] HANDOFF.md: {X lines}
[PASS/WARN] README.md: {status}
[PASS/WARN] CLAUDE.md: {status}

OVERALL: READY TO COMMIT / ISSUES TO ADDRESS

{If issues, list them with recommended actions}
```

## Rules

- Report ALL issues, even minor ones
- Do NOT auto-fix anything
- Do NOT skip checks
- Do NOT run test suite (use `/test-focus` if needed)
- BLOCK commit if Check 2 (secrets) fails
- User decides whether to commit with non-secret issues or fix first
