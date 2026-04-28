---
description: "Review staged/unpushed changes for soundness before committing or pushing. Catches regressions, dead code, broken contracts, and integration issues."
argument-hint: "[base-ref] (default: origin/main or last pushed commit)"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Agent"]
---

# Review Changes

Review local changes (staged, committed but unpushed, or a specific range) for soundness. This is not a linter or style checker — it catches issues that emerge from iteration: dead code left behind, broken error contracts, unintended behavioral changes, and integration gaps between layers.

**Scope:** $ARGUMENTS (default: all unpushed commits on current branch vs origin)

## Phase 1: Gather Context

1. **Determine diff scope:**
   ```bash
   # Use argument if provided, otherwise detect unpushed changes
   BASE=${ARGUMENTS:-$(git rev-parse @{upstream} 2>/dev/null || echo origin/main)}
   git log --oneline $BASE..HEAD
   git diff --stat $BASE..HEAD
   ```

2. **Read project standards:**
   - `CLAUDE.md` (root + nested)
   - `CONTRIBUTING.md`

3. **Identify the full diff:**
   ```bash
   git diff $BASE..HEAD
   ```

4. **Categorize changed files** to determine which review agents are relevant.

## Phase 2: Launch Review Agents

Launch **all applicable agents in parallel**. Each agent gets the full diff and project standards. Skip agents whose concerns don't apply to the changed files.

### Agent 1: Error Flow & Contract Integrity

**When to include:** Changes touch error handling, retry logic, classification functions, or multi-layer call chains.

**Prompt:**

> You are reviewing changes for error flow integrity. The repository is at {CWD}. Review the diff between `{BASE}` and HEAD.
>
> **Project standards:** {CLAUDE.md + CONTRIBUTING.md content}
>
> **Focus areas:**
> - Trace errors end-to-end: from where they're thrown to where they're finally caught. Does every catch site receive the error type it expects? If any intermediate layer wraps, formats, or re-throws, do downstream handlers still recognize the error?
> - Check for broken contracts: if function A throws ErrorType X, and function B catches and classifies by instanceof, does any layer in between transform X into something B won't recognize?
> - Verify retry/fallback gates: for each retry or fallback path, trace what error type triggers it and confirm that error can actually reach the gate in its expected form.
> - Look for swallowed errors: catch blocks that log but don't re-throw, or that catch too broadly and hide failures.
> - Check `.cause` chain preservation: if errors are wrapped, is `.cause` set so that classifiers can traverse?
>
> **How to review:**
> 1. Read the full diff
> 2. For each error-handling change, read the full file for context
> 3. Trace the call path from throw site → intermediate handlers → final catch
> 4. Verify that the error type at each handler matches what it checks for
>
> **Output:** Structured findings with severity, file:line, issue, and suggestion.

### Agent 2: Dead Code & Leftover Artifacts

**When to include:** Always (iteration commonly leaves behind dead code).

**Prompt:**

> You are reviewing changes for dead code and iteration artifacts. The repository is at {CWD}. Review the diff between `{BASE}` and HEAD.
>
> **Project standards:** {CLAUDE.md + CONTRIBUTING.md content}
>
> **Focus areas:**
> - Unreachable code: conditions that can never be true given the new logic, branches that are shadowed by earlier returns.
> - Unused imports/exports: new imports that aren't used, exports that nothing references after the change.
> - Orphaned variables: variables declared but never read, or assigned but the assignment is overwritten before use.
> - Leftover from iteration: commented-out code, TODO comments that reference completed work, debug logging that shouldn't ship.
> - Redundant checks: conditions that duplicate what a called function already guarantees.
> - Constants/config that are no longer referenced after the change.
>
> **How to review:**
> 1. Read the full diff
> 2. For each new function, export, type, or constant — grep the codebase for usages
> 3. For each new condition or branch — trace whether it can actually be reached
> 4. For each removed code path — check if anything else depended on it
>
> **Output:** Structured findings with severity, file:line, issue, and suggestion.

### Agent 3: Behavioral Regression Check

**When to include:** Always for non-trivial changes.

**Prompt:**

> You are reviewing changes for unintended behavioral regressions. The repository is at {CWD}. Review the diff between `{BASE}` and HEAD.
>
> **Project standards:** {CLAUDE.md + CONTRIBUTING.md content}
>
> **Focus areas:**
> - Changed function signatures: did the return type, parameter types, or semantics change in a way that callers don't expect?
> - Changed defaults: did a default value change? Trace all callers that rely on the old default.
> - Narrowed or widened behavior: does a function now handle fewer cases than before (regression) or more cases than intended (over-broad)?
> - Variable type changes: `const` → `let`, narrower type → wider type, guaranteed-assigned → possibly-undefined.
> - Ordering changes: did the order of operations change? Does anything depend on the old order?
> - Existing tests: run `npm test` (or equivalent) and verify all pass. If tests were removed or modified, verify the removal was intentional and not masking a regression.
>
> **How to review:**
> 1. Read the full diff carefully
> 2. For each changed function, read its callers (grep for usage) — do they still work with the new behavior?
> 3. For each changed type or interface, check all implementations and usages
> 4. Run the test suite and report results
>
> **Output:** Structured findings with severity, file:line, what changed, who's affected, and whether it's intentional.

### Agent 4: Integration & Layer Consistency

**When to include:** Changes span multiple files or layers (e.g., lib + caller, types + implementation).

**Prompt:**

> You are reviewing changes for cross-layer consistency. The repository is at {CWD}. Review the diff between `{BASE}` and HEAD.
>
> **Project standards:** {CLAUDE.md + CONTRIBUTING.md content}
>
> **Focus areas:**
> - Type agreement: if a type definition changed, do all producers and consumers of that type align?
> - API contract: if a function's behavior changed, do all callers pass the right arguments and handle the new return value/errors?
> - Config propagation: if a constant, env var, or config value was added/changed, is it set in all environments (dev, staging, prod, Docker, .env.example)?
> - Import consistency: if a module's exports changed, are all importers updated?
> - Feature flags / conditional paths: if a new path was added (fallback, retry, mode), does it integrate correctly with existing paths? Can you reach an inconsistent state?
>
> **How to review:**
> 1. Read the full diff
> 2. For each changed export or type, grep for all importers and verify they're compatible
> 3. For each new env var or config, check Dockerfile, docker-compose, .env.example, deployment docs
> 4. Trace data flow across the changed layers — verify the contract between them is consistent
>
> **Output:** Structured findings with severity, file:line, issue, and suggestion.

## Phase 3: Synthesize

After all agents complete:

1. **Deduplicate** — multiple agents may flag the same issue from different angles. Merge into one finding.

2. **Cross-reference** — look for compound issues:
   - Dead code + broken contract = a path that used to work is now unreachable
   - Regression + missing test = unprotected behavioral change
   - Layer inconsistency + error flow issue = errors that can't be properly handled

3. **Verify Critical/Major findings** — read the code yourself before reporting. Agent findings are hypotheses. Confirm or drop.

4. **Run tests** if not already done by an agent:
   ```bash
   npm run typecheck && npm test
   ```

5. **Organize into report**

## Report Format

```
## Review: [N] commits, [M] files changed

### Critical ([count])
Will cause bugs or break existing functionality.
[file:line — description — fix]

### Major ([count])
Should fix before pushing — correctness, dead code, broken contracts.
[file:line — description — fix]

### Minor ([count])
Worth fixing, not blocking.
[file:line — description]

### Verification
- Tests: [pass/fail status]
- Typecheck: [pass/fail status]
```

## Adding New Agents

To add a new review dimension, add a new `### Agent N` section to Phase 2 with:
- **When to include:** condition for when this agent is relevant
- **Prompt:** what to look for, how to review, output format

The synthesis phase automatically incorporates findings from any agent that runs.
