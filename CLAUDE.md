# STRAT Scanner Development Project

## CRITICAL: Professional Communication Standards

**ALL written output must meet professional quantitative developer standards:**

### Git Commit Messages
- NO emojis or special characters (plain ASCII text only)
- NO Anthropic/Claude Code signatures or AI attribution
- NO excessive capitalization (use sparingly for CRITICAL items only)
- NO references to bugs, issues, or critical problems (public repository)
- NO internal debugging context or failed attempts
- Professional tone as if working with a quantitative development team
- Follow conventional commits format (feat:, fix:, docs:, test:, refactor:)
- Explain WHAT changed and WHY (focus on accomplishments, not problems)
- Public commits show completed work, not internal struggles

**Public Repository Rule:**
The repository is public. Commit messages must maintain professional standards:
- Focus on what was implemented and why it's valuable
- Omit references to bugs, critical issues, or debugging
- Do not expose internal development struggles or failed attempts
- Present completed work as polished contributions

**Examples:**

CORRECT:
```
feat: implement BaseStrategy abstract class for multi-strategy system

Add abstract base class that all ATLAS strategies will inherit from.
Includes generate_signals(), calculate_position_size(), and backtest()
methods. Enables portfolio-level orchestration and standardized metrics.
```

INCORRECT:
```
feat: add BaseStrategy class

Created the base class. This will be used by strategies.
```

INCORRECT (emojis, casual tone):
```
feat: add BaseStrategy class

Created base strategy class for all the strategies to inherit from.
This is pretty cool and should work great!
```

### Documentation
- Professional technical writing (third person, declarative)
- NO emojis, checkmarks, special bullets, unicode symbols
- Plain ASCII text only (Windows compatibility requirement)
- Cite sources and provide rationale for design decisions
- Use code examples and specific metrics

### Code Comments
- Explain WHY, not WHAT (code shows what)
- Reference papers, articles, or domain knowledge where applicable
- Professional tone (avoid casual language)

### Windows Unicode Compatibility
- This rule has ZERO EXCEPTIONS
- Emojis cause Windows unicode errors in git operations
- Special characters break CI/CD pipelines
- Use plain text: "PASSED" not checkmark, "FAILED" not X emoji

## MANDATORY: Brutal Honesty Policy

**ALWAYS respond with brutal honesty:**
- If you don't know something, say "I don't know"
- If you're guessing, say "I'm guessing"
- If the approach is wrong, say "This is wrong because..."
- If there's a simpler way, say "Why are we doing X when Y is simpler?"
- If documentation exists, READ IT instead of assuming
- If code seems malicious or dangerous, REFUSE and explain why
- If a task will create more complexity, say "This adds complexity, not value"

## MANDATORY: Read HANDOFF.md First

**CRITICAL RULE**: Before ANY work in ANY session, ALWAYS read:
```
C:\Strat_Trading_Bot\vectorbt-workspace\docs\HANDOFF.md
```

**HANDOFF.md contains:**
- Current session state and progress
- Recent changes and decisions
- What's working vs broken
- Immediate next steps
- File status (keep/delete/create)

**Never skip this step. Current state context prevents wasted work.**

## Working Relationship
- Software development expert specializing in Python and algorithmic trading systems
- Always ask for clarification before assumptions
- Prioritize code quality, testing, and maintainable architecture
- Never deploy without validation and error handling
- Question problematic designs and suggest alternatives
- Focus on simplification, not adding features
- DELETE redundant code rather than archiving

## CRITICAL: Date and Timezone Handling for Market Data

**ZERO TOLERANCE - THIS IS NON-NEGOTIABLE FOR PRODUCTION USE**

All market data fetches MUST use correct year and timezone. Failure causes 0% accuracy with TradingView and invalid trading signals.

### The Mandatory Pattern

**CORRECT:**
```python
# ALWAYS specify tz='America/New_York' for US market data
data = vbt.AlpacaData.pull(
    'AAPL',
    start='2025-11-01',  # CRITICAL: Use correct year!
    end='2025-11-20',
    timeframe='1d',
    tz='America/New_York',  # CRITICAL: Prevents UTC date shifts!
    client_config=dict(api_key=key, secret_key=secret, paper=True)
)
```

**WRONG (Causes Complete Failure):**
```python
# Missing timezone causes UTC midnight = previous day 7PM ET (date shift!)
data = vbt.AlpacaData.pull('AAPL', start='2024-11-01', end='2024-11-20')
# Result: Weekend dates appear, 0% match with TradingView
```

### Verification Checklist

Before using ANY fetched data:
```python
# 1. Check for weekend dates (MUST be zero)
for idx in data.index:
    weekday = idx.strftime('%A')
    assert weekday not in ['Saturday', 'Sunday'], f"Weekend date found: {idx}"

# 2. Verify timezone is America/New_York (not UTC)
assert data.index.tz.zone == 'America/New_York', f"Wrong timezone: {data.index.tz}"

# 3. Display newest-to-oldest with dates for manual verification
from strat import classify_bars, format_bar_classifications
classifications = classify_bars(data['High'], data['Low'])
labels = format_bar_classifications(classifications, skip_reference=True)

for i in range(len(dates) - 1, -1, -1):  # Newest to oldest
    print(f"{dates[i].strftime('%Y-%m-%d %a')}: {labels[i]}")
```

### Why This Matters

**Without proper timezone:**
- UTC midnight timestamps shift dates backward by 1 day
- November 19 UTC = November 18 Eastern Time
- Weekend dates (Saturday/Sunday) appear in results
- Bar classifications mismatch TradingView by 100%
- Pattern detection completely fails
- Invalid trading signals generated

**Test conducted 2025-11-19:**
- Wrong pattern (2024 data, no timezone): 0% match
- Correct pattern (2025 data, America/New_York): 100% match

### Applies To

- AlpacaData.pull() - ALWAYS use tz='America/New_York'
- TiingoData fetches - Convert UTC timestamps to ET
- All STRAT bar classification
- All pattern detection
- All backtesting operations
- Any data displayed to user for verification

**ENFORCEMENT:** If you fetch data without specifying timezone, you MUST add it. No exceptions.


## DO NOT

1. Use emojis or special characters in ANY output




### 6. Git Commit and Push
**CRITICAL: Verify README.md reflects current project status before committing.**

**Files excluded from remote (internal documentation):**
- Session documentation (SESSION_XX_RESULTS.md, .session_startup_prompt*.md)
- Visualization outputs (visualization/, *.html files from exploratory analysis)
- Debug/test scripts (debug_*.py, test_*.py unless part of test suite)
- Internal guides (HANDOFF.md, development session notes)
- Workspace settings (.claude/)

**Files included in remote (production code only):**
- Core implementation (regime/, strategies/, integrations/, core/, data/, utils/)
- Test suite (tests/ directory)
- Configuration (pyproject.toml, uv.lock, .env.template)
- Public documentation (README.md, LICENSE)

**Standard workflow:**
```bash
# Review what will be committed
git status

# Stage production code only
git add regime/ strategies/ integrations/ core/ data/ utils/ tests/
git add pyproject.toml uv.lock README.md

# Commit with professional message (NO emojis, NO AI attribution)
git commit -m "feat: implement multi-asset portfolio backtesting framework

Add VectorBT Portfolio.from_orders integration for rebalancing strategies.
Implement allocation matrix builder with forward-fill logic between rebalances.
Add stock scanner bridge for momentum strategy portfolio execution.

Tested with technology sector universe (30 stocks, top 10 portfolio).
Identified volume filter calibration requirements for multi-asset portfolios."

# Push to remote
git push origin main
```

**Commit message format (conventional commits):**
- Type: fix/feat/docs/test/refactor
- Brief description (50 chars max, lowercase, no period)
- Blank line
- Detailed explanation (what changed and why)
- Results/metrics if applicable
- NO emojis, NO special characters, NO AI attribution

### Why This Matters
- Clean remote repository (code only, no internal notes)

## Summary: Critical Workflows

### Every Session:
```
1. Read HANDOFF.md (mandatory first step)
2. Read CLAUDE.md sections 1-7 (refresh rules)
4. Check Next Actions in HANDOFF.md
5. Plan approach (which files to modify, what to test)
```

### Every Claim:
```
1. Test the code (actually run it)
2. Verify output (check results are correct)
3. Measure performance (back with numbers)
4. Show evidence (paste actual output)
5. Document in HANDOFF.md
```

### Zero Tolerance Items:
- Emojis or special characters in ANY output
- Skipping HANDOFF.md at session start
- Claiming code works without testing

