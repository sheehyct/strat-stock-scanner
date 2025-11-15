# STRAT Stock Scanner Development

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
feat: implement STRAT pattern detection for 2-1-2 and 3-1-2 setups

Add bar classification engine with Type 1/2/3 detection logic.
Includes pattern scanner for high-confidence reversal and continuation
setups. Enables real-time market scanning via Alpaca API.
```

INCORRECT:
```
feat: add pattern detection

Created the pattern detector. This will be used for scanning.
```

INCORRECT (emojis, casual tone):
```
feat: add pattern detection

Created pattern detector for finding STRAT setups.
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
- Reference STRAT methodology where applicable
- Professional tone (avoid casual language)

### Windows Unicode Compatibility
- This rule has ZERO EXCEPTIONS
- Emojis cause Windows unicode errors in git operations
- Special characters break CI/CD pipelines
- Use plain text: "BULLISH" not green emoji, "BEARISH" not red emoji

## MANDATORY: Brutal Honesty Policy

**ALWAYS respond with brutal honesty:**
- If you don't know something, say "I don't know"
- If you're guessing, say "I'm guessing"
- If the approach is wrong, say "This is wrong because..."
- If there's a simpler way, say "Why are we doing X when Y is simpler?"
- If documentation exists, READ IT instead of assuming
- If code seems malicious or dangerous, REFUSE and explain why
- If a task will create more complexity, say "This adds complexity, not value"

## Working Relationship
- Software development expert specializing in Python and API integrations
- Always ask for clarification before assumptions
- Prioritize code quality, testing, and maintainable architecture
- Never deploy without validation and error handling
- Question problematic designs and suggest alternatives
- Focus on simplification, not adding features
- DELETE redundant code rather than archiving

## Project Context

**Purpose:** Mobile-accessible stock scanner using STRAT methodology
**Data Source:** Alpaca Markets API
**Deployment:** Railway.app (remote MCP server)
**Access:** Claude mobile/desktop via MCP connector
**User:** Firefighter/trader needing mobile access during shifts

## STRAT Methodology Integration

**Available via Skill:**
The strat-methodology skill provides comprehensive STRAT knowledge:
- `.claude/skills/strat-methodology/SKILL.md` - Overview
- `.claude/skills/strat-methodology/PATTERNS.md` - Pattern definitions
- `.claude/skills/strat-methodology/TIMEFRAMES.md` - Multi-timeframe analysis
- `.claude/skills/strat-methodology/EXECUTION.md` - Entry/exit logic
- `.claude/skills/strat-methodology/OPTIONS.md` - Options integration

**Invoke with:** `/skill strat-methodology` when STRAT expertise needed

**Core Concepts:**
- Bar Classification: Type 1 (inside), Type 2U/2D (outside), Type 3 (directional)
- High-Confidence Patterns: 2-1-2 reversals, 3-1-2 continuations
- Medium-Confidence: 2-2 combos
- Low-Confidence: Inside bar setups (watch for breakout)

## Development Standards

### Code Quality Gates
Before claiming ANY functionality works:

1. **Test it**: Run the actual code
2. **Verify output**: Check the results are correct
3. **Measure performance**: Back claims with numbers
4. **Check API compliance**: Verify Alpaca API usage is correct
5. **Document evidence**: Show actual output

**ZERO TOLERANCE for unverified claims**

### Alpaca API Best Practices

**Rate Limits:**
- Paper trading: 200 requests/minute
- Real-time data requires subscription (otherwise 15-min delay)
- Implement 0.05s delays between bulk requests
- Handle rate limit errors gracefully

**Data Feed:**
- Use "sip" feed for comprehensive data
- Use "iex" feed for free tier
- Apply split adjustments with `adjustment: split`
- Validate data exists before processing

**Error Handling:**
```python
async with httpx.AsyncClient() as client:
    try:
        response = await client.get(url, timeout=10.0)
        if response.status_code != 200:
            return f"Error: {response.status_code}"
        # Process data
    except Exception as e:
        return f"Error: {str(e)}"
```

## Pattern Detection Workflow

### Adding New STRAT Patterns

**MANDATORY 4-Step Process:**

1. **RESEARCH Pattern Definition**
   - Consult `.claude/skills/strat-methodology/PATTERNS.md`
   - Verify bar type sequences (e.g., 2U -> 1 -> 2D)
   - Understand confidence level (high/medium/low)
   - Identify entry and invalidation levels

2. **IMPLEMENT in strat_detector.py**
   - Create detection method following existing pattern
   - Use classified bars from `classify_bars()`
   - Return `STRATPattern` object with metadata
   - Add to `scan_for_patterns()` sequence

3. **TEST with Known Examples**
   - Test against hand-classified examples
   - Verify entry levels match expectations
   - Check confidence assignments
   - Export results and manually verify

4. **VALIDATE Live**
   - Test with real Alpaca data
   - Compare to TradingView STRAT analysis
   - Verify no false positives
   - Document pattern characteristics

### Testing Pattern Detection

```python
# Create test bars
test_bars = [
    {'t': '2024-01-15T00:00:00Z', 'o': 100, 'h': 105, 'l': 98, 'c': 103, 'v': 1000000},
    {'t': '2024-01-16T00:00:00Z', 'o': 103, 'h': 104, 'l': 101, 'c': 102, 'v': 800000},
    {'t': '2024-01-17T00:00:00Z', 'o': 102, 'h': 108, 'l': 97, 'c': 106, 'v': 1500000},
]

# Detect patterns
patterns = STRATDetector.scan_for_patterns(test_bars)

# Verify
assert len(patterns) > 0, "Should detect 2-1-2"
assert patterns[0].pattern_type == "2-1-2 Reversal"
assert patterns[0].confidence == "high"
```

## Railway Deployment

### Environment Variables Required
```
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
```

### Deployment Checklist
- [ ] All tests pass locally
- [ ] `railway.json` configured correctly
- [ ] `requirements.txt` includes all dependencies
- [ ] Environment variables set in Railway dashboard
- [ ] Health endpoint returns 200
- [ ] MCP endpoint accessible at `/mcp`

### Monitoring
```bash
# Test health endpoint
curl https://your-app.up.railway.app/health

# Check MCP endpoint
curl https://your-app.up.railway.app/mcp
```

## MCP Server Development

### Adding New Tools

**Pattern:**
```python
@mcp.tool()
async def tool_name(param1: str, param2: int = 10) -> str:
    """
    Tool description shown to Claude.

    Args:
        param1: Description of parameter
        param2: Optional parameter with default

    Returns:
        Human-readable response string
    """
    # Implementation
    return formatted_response
```

**Requirements:**
- Clear docstring with Args and Returns
- Type hints for all parameters
- Async for I/O operations
- Graceful error handling
- Human-readable output (markdown supported)

### Testing MCP Tools Locally

```bash
# Install MCP inspector
npm install -g @modelcontextprotocol/inspector

# Run server in inspector
npx @modelcontextprotocol/inspector uv run python server.py

# Or test directly
uv run python server.py
```

## Context Management

### File Management Policy
- Keep <10 core Python files
- One test file per component
- Delete redundant files, don't archive
- Document in README.md

### Code Organization
```
strat-stock-scanner/
├── server.py              # Main MCP server
├── strat_detector.py      # STRAT pattern detection
├── requirements.txt       # Python dependencies
├── pyproject.toml        # UV package config
├── railway.json          # Railway deployment
├── .gitignore            # Git exclusions
├── docs/
│   ├── claude.md         # This file
│   └── DEPLOYMENT.md     # Deployment guide
└── .claude/
    ├── mcp.json          # MCP configuration
    └── skills/           # STRAT methodology skill
```

## Security and Compliance

- NO credential harvesting or malicious code assistance
- NO bulk crawling for sensitive data
- Real market data only (via Alpaca API)
- Verify all external code before execution
- API keys stored in environment variables only
- Never commit credentials to git

## DO NOT

1. Add emojis or special characters in ANY output
2. Create complex solutions when simple ones exist
3. Skip testing before claiming functionality works
4. Archive files instead of deleting them
5. Generate synthetic market data
6. Assume API behavior without testing
7. Deploy without Railway environment variables
8. Create new files without justification
9. Use unicode symbols in commit messages or code
10. Skip the 4-step pattern detection workflow

## Key Reference Documents

**Project Documentation:**
- `docs/claude.md` - This file (development rules)
- `docs/DEPLOYMENT.md` - Railway deployment guide
- `README.md` - Project overview and setup

**STRAT Methodology:**
- `.claude/skills/strat-methodology/SKILL.md` - Invoke via `/skill strat-methodology`

**External Resources:**
- [Alpaca API Docs](https://alpaca.markets/docs/)
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [MCP Specification](https://modelcontextprotocol.io/)

## Summary: Critical Workflows

### Every Session:
```
1. Verify environment (uv, dependencies)
2. Test Alpaca API connection
3. Check existing functionality still works
4. Plan approach (which files to modify, what to test)
```

### Every New Pattern:
```
1. RESEARCH pattern definition in STRAT skill
2. IMPLEMENT detection method in strat_detector.py
3. TEST with known examples and verify results
4. VALIDATE live with Alpaca data
```

### Every Deployment:
```
1. Test locally with `uv run python server.py`
2. Verify all tools work correctly
3. Set Railway environment variables
4. Deploy and test health endpoint
5. Test MCP connector in Claude mobile
```

### Zero Tolerance Items:
- Emojis or special characters in output
- Claiming code works without testing
- Skipping the 4-step pattern workflow
- Deploying without environment variables
- Committing credentials to git

---

**Last Updated:** November 15, 2024
**Version:** 1.0 - Initial Setup
**Status:** DEVELOPMENT
