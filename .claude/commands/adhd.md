---
name: adhd
description: Mid-session recap of a paused or resumed session, in plain English, from the live conversation only
---

# /adhd - mid-session recap

A session was paused, possibly for days, and is now being resumed. Every other
continuity layer here - docs/HANDOFF.md, /session-start, /session-end,
OpenMemory - fires at session BOUNDARIES. A paused live session exists only in
this context window. This command re-enters it.

## Hard constraint: read nothing

Use NO tools. No Read, no Grep, no Glob, no Bash, no git, no OpenMemory, no
HANDOFF.md, no transcripts, no web. Answer entirely from the conversation
already in this context window.

This is the point of the command, not a shortcut. The live conversation is the
only ground truth for what happened inside it. Reading files would report what
the repo looks like now, which is a different question and is what
/session-start already answers. If something is genuinely not in context, write
"not in context" and move on. Do not go find it.

Do not resume work. Report, then stop. The user decides what happens next.

## Two checks before the recap

- If the conversation has been compacted - earlier turns appear as a summary
  rather than as the original messages - say so in ONE line at the very top, so
  the user knows early detail may survive only in summarized form. Then
  continue normally.
- If the session has barely started and there is nothing to recap, say that in
  one line and stop. Do not manufacture a recap.

## Output - these six sections, in this order, nothing before them

**1. Situation.** Two or three sentences: what this session is about and what
was set out to do.

**2. Done so far.** Short list, one line per item. What is actually finished,
not what was attempted.

**3. Right now.** The exact current state. Mid-edit in which file. Tests
failing and which. Blocked on what. Waiting on a decision from the user, and
which decision. Be specific enough to pick the work back up from this line
alone.

**4. Decisions.** Two explicitly separate lists.

  **(a) Decided by the user** - what they chose, in their words where possible.

  **(b) Chosen or defaulted to WITHOUT the user's explicit sign-off** - this is
  the important list and the reason the section exists. It includes: picking one
  approach, library, name, or file layout when more than one was reasonable;
  choosing a default value, threshold, or edge-case behavior; deciding what NOT
  to do, or quietly narrowing scope; interpreting an ambiguous instruction one
  way; deferring something without flagging it; resolving a conflict between a
  spec and the actual code by preferring one of them.

  If list (b) comes out empty, that is almost certainly a reporting failure
  rather than a fact - re-scan the session before concluding it. A session with
  real work in it and no unilateral choices is rare.

**5. Next action.** Exactly one. Not three, not a ranked list. One thing that
can be started immediately.

**6. Parking lot.** Ideas raised during the session that are not current scope.
Label them plainly as not current scope so they are not mistaken for pending
work.

## The jargon rule

Every term of art - engineering or trading - is either avoided or unpacked in
one clause at first use. The test: the user, four days from now, tired, reading
this on a phone, should never have to ask what a word means.

The deeper rule: **shared vocabulary is not evidence of shared understanding.**
Restate mechanics, not labels. A label reads identically whether the code
implements the user's rules or the textbook's, so a label proves nothing.

This sentence is exactly what the command exists to forbid:

> "Implemented the 2-2 continuation with TFC gating."

The replacement must describe what THIS session's code actually does, in
mechanics. Shape of the fix, illustrative only - do not reuse the wording:

> "It now fires when two bars in a row each break one side only of the bar
> before them, both in the same direction, and it stays quiet unless the other
> timeframes we check are pointing the same way."

Same rule for engineering terms. "Added a debounce" becomes "if it gets called
again within N milliseconds, the earlier call is dropped and only the last one
runs."

## Strategy mode

Trigger this automatically whenever the session involved trading-strategy
implementation, STRAT logic, or the user teaching a strategy. When in doubt,
include it. Append to the recap, after section 6:

**Rules as actually implemented.** A jargon-banned restatement of what the code
does - not what was discussed, not what was intended. Where the code and the
conversation disagree, say so; that gap is the finding.

**A worked trace.** Take one concrete input, walk it through the real code
path, and narrate in plain English what fires and why. Name the actual
functions and files. Prefer an input sitting at an edge case where house rules
could diverge from canonical STRAT: how a break is defined, equal highs or
lows, a gating boundary, the first or last bar of a set.

Use a real input from the session's context if one exists. If none does, say
"no real input in context" and construct one, labeled clearly as constructed.
Never present an invented input as if it came from the session, and never name
a function that was not actually seen in this session - a fabricated trace is
worse than no trace, because a paraphrase can be faked fluently and a trace
against real code cannot.

## Length and tone

Sections 1-6: under about 300 words total. The strategy addendum may run
longer; the trace needs room to be specific.

No preamble. No "here is your recap". No summary of the summary at the end. No
emojis, plain ASCII only. Start at section 1.
