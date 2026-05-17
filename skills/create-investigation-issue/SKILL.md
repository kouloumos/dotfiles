---
name: create-investigation-issue
description: Create a GitHub issue documenting a technical investigation / root cause analysis. Use after debugging sessions where significant investigation was done and context needs to be preserved for the team.
argument-hint: <optional: brief description of the investigated problem>
---

# Create Investigation Issue

Create well-structured GitHub issues that document the findings of a technical investigation. Unlike simple bug reports ("X is broken, here's how to reproduce"), investigation issues preserve the **reasoning chain** and **evidence** so the team understands not just what's wrong, but why, how we know, and what the options are.

## When to use this (vs create-issue)

Use this skill when:
- Significant debugging/investigation has already been done in the conversation
- The root cause is understood (or narrowed down)
- The context would be lost without documentation
- Multiple team members need to understand the problem to fix it or avoid regressions

Use `create-issue` instead for: simple bug reports, feature requests, tasks, or issues where the cause is obvious.

## Determine the Repository

Use the current git repo by default:

```bash
gh repo view --json nameWithOwner -q .nameWithOwner
```

If `$ARGUMENTS` includes a repo reference, use that instead.

## Search for Related Issues

Before drafting, ALWAYS search GitHub for related existing issues:

```bash
gh search issues "<relevant keywords>" --repo <REPO> --limit 5
```

If related issues exist, present them and confirm this is distinct.

## Fetching Labels

```bash
gh label list --repo <REPO> --limit 50
```

Use actual labels returned. Do not assume label names.

## Writing Principles

**Progressive disclosure.** The issue should be readable in 30 seconds (Summary + Root Cause) but exhaustive if you keep reading (Evidence + Investigation Trail). Use collapsible `<details>` sections for supporting material.

**Dual purpose.** The top half (Summary, Impact, Root Cause, Fix Options) is the actionable ticket. The bottom half (Evidence, Investigation Trail) is lasting documentation. Both live in one artifact.

**Precision over brevity.** Name specific files, functions, configuration values, and mechanisms. Link to code when possible. Vague descriptions ("the cache is slow") don't help future investigators.

**Separate observation from interpretation.** Evidence is what you measured/observed. Root Cause is your interpretation of why. Keep them distinct so readers can validate your reasoning.

**Fix options, not prescriptions.** Present approaches with tradeoffs. Let the implementer choose. Note which options address symptoms vs causes.

## Issue Structure

```markdown
## Summary
[2-3 sentences: what's broken, who's affected, severity. Inverted pyramid — most important info first.]

## Impact
- **Affected**: [users/flows/frequency]
- **Since**: [when it started or was introduced]
- **Severity**: [data loss / degraded experience / cosmetic]

## Background
[Only if the reader needs context to understand the Root Cause. Explain relevant system mechanics,
architecture, or interactions that aren't common knowledge. Skip if the root cause is self-explanatory.]

## Root Cause
[The technical mechanism. Be specific: which components interact, under what conditions, to produce
the failure. Name files, config values, code paths. Explain contributing factors and how they interact.]

[If relevant: "Why this didn't happen before X" — helps the team understand what changed.]

<details>
<summary>

## Evidence

</summary>

[Logs, queries, measurements, reproduction data. Whatever proves the root cause claim.
Include timestamps, exact values, command output. This is the "show your work" section.]

</details>

## Fix Options

| # | Approach | Effort | Addresses |
|---|----------|--------|-----------|
| 1 | ... | Low/Med/High | What it fixes (symptom vs cause) |
| 2 | ... | ... | ... |

[Optional: note which combination of options fully resolves the issue]

<details>
<summary>

## Investigation Trail

</summary>

[Chronological narrative of how you arrived at the root cause. Include hypotheses that were
ruled out and why — this prevents re-investigation and teaches future debuggers.]

1. Observed [symptom] in [context]
2. Hypothesized [X] — ruled out because [evidence]
3. Hypothesized [Y] — confirmed by [evidence]
4. ...

</details>
```

## Section Guidelines

### Summary
- Lead with the user-visible symptom, not the technical mechanism
- Include severity and scope
- A reader should know whether this affects them after reading only this section

### Background
- Only include if the root cause requires understanding non-obvious system mechanics
- Explain "how things work" before "how things broke"
- Use concrete examples (actual cache entries, actual tag arrays) rather than abstract descriptions
- Skip entirely if the root cause is self-explanatory to the team

### Root Cause
- Name the contributing factors explicitly (usually 2-3 things interacting)
- Be specific: file paths, config values, function names, version numbers
- Explain the mechanism step by step
- If something changed recently that triggered the issue, call it out

### Evidence
- Collapsible — keeps the issue scannable
- Include raw data: command output, log lines, measurements
- Label what each piece of evidence proves

### Fix Options
- Table format for quick comparison
- Note effort level honestly
- Distinguish "fixes the symptom" from "fixes the cause"
- Don't recommend one option — let the team decide based on current priorities

### Investigation Trail
- Collapsible — valuable for learning, not needed for fixing
- Include dead ends (hypotheses ruled out) — prevents re-investigation
- Chronological order
- Brief: one line per step unless a step needs explanation

## Workflow

### Step 1: Gather from conversation
Review the conversation for:
- The symptoms observed
- Hypotheses tested and ruled out
- The confirmed root cause and evidence
- Fix options discussed

If key information is missing, ask focused questions (max one round).

### Step 2: Generate Preview
Show the user a formatted preview of the full issue. Ask:
"Reply **yes** to create, **edit** to change something, or **cancel** to abort."

### Step 3: Create the Issue
After user confirms:

```bash
gh issue create --repo <REPO> --title "<TITLE>" --body "<BODY>" --label "<label1>" --label "<label2>"
```

Report the issue URL back to the user.

## Guidelines
- NEVER create an issue without showing a preview and getting explicit approval
- Title should describe the symptom, not the cause (e.g., "Stale meeting data served to regular users" not "HSCAN timeout in cache handler")
- Always include the Investigation Trail — it's what makes this format valuable over a simple bug report
- If the conversation didn't produce clear evidence or root cause, fall back to `create-issue` format instead
