---
description: "Deep PR review using parallel specialized agents. Use before merging to catch real issues."
argument-hint: "[base-branch]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Agent"]
---

# Deep PR Review

Run a thorough pull request review using parallel domain-specialized agents, each bringing deep expertise to a different aspect of the code. This is not a linter — it catches the issues that only an experienced reviewer would find.

**Base branch:** $ARGUMENTS (default: auto-detect from `main` or `master`)

## Phase 1: Gather Context

Before launching agents, collect the information they all need.

1. **Detect base branch:**
   ```bash
   # Use argument if provided, otherwise detect
   git remote | grep -q upstream && BASE=upstream/main || BASE=origin/main
   # Fallback to main or master
   git rev-parse --verify $BASE 2>/dev/null || BASE=main
   git rev-parse --verify $BASE 2>/dev/null || BASE=master
   ```

2. **Collect PR scope:**
   ```bash
   git log --oneline $BASE..HEAD
   git diff --stat $BASE..HEAD
   ```

3. **Read project standards** (if they exist):
   - `CLAUDE.md` (root and any nested ones in changed directories)
   - `CONTRIBUTING.md`
   
   These are passed to agents as context for project-specific rules.

4. **Identify changed file categories** to determine which agents are relevant:
   - Schema/migration files (`.prisma`, `migration.sql`)
   - Business logic (`src/lib/`, `lib/`, `services/`, `utils/`)
   - API routes / handlers (`src/app/api/`, `pages/api/`, `routes/`)
   - UI components (`src/components/`, `components/`)
   - Test files (`__tests__/`, `*.test.*`, `*.spec.*`)
   - Config files (`package.json`, `tsconfig.json`, `flake.nix`, etc.)

## Phase 2: Launch Specialized Review Agents

Launch **all applicable agents in parallel** using a single message with multiple Agent tool calls. Each agent gets the full diff for its domain plus the project standards.

Skip agents whose domain has no changed files (e.g., skip the schema agent if no schema files changed).

### Agent 1: Data Layer & Schema Review

**When to include:** Schema files, migrations, seed files, ORM config, or database query files changed.

**Prompt template for the agent:**

> You are an expert database and data layer reviewer. Review the changes on branch HEAD vs `{BASE}` in this repository.
>
> **Project standards (apply these rules):**
> {CLAUDE.md and CONTRIBUTING.md content, if they exist}
>
> **Your focus areas:**
> - Schema correctness: naming, relations, indexes, constraints, composite keys
> - Migration safety: data loss risks, backwards compatibility, additive-only vs destructive
> - Query patterns: N+1 queries, missing indexes for query patterns, transaction boundaries
> - Seed data: consistency with schema, type handling (dates, enums), relation integrity
> - ORM usage: proper typing, connection handling, raw query safety
>
> **How to review:**
> 1. Run `git diff {BASE}..HEAD` filtered to relevant files to see the changes
> 2. For each changed file, also read the full file for context (not just the diff)
> 3. When reviewing queries, check if the fields being queried have appropriate indexes
> 4. For migrations, verify they are safe to run on a production database with data
>
> **Output format:**
> Return a structured list of findings. For each finding:
> - **Severity**: Critical / Major / Minor / Nit
> - **File**: exact path and line number
> - **Issue**: what's wrong
> - **Suggestion**: how to fix it
>
> Be thorough but practical. Flag real problems, not style preferences. If you find no issues in a category, don't fabricate them.

### Agent 2: Business Logic & Correctness Review

**When to include:** Always (any non-trivial PR has logic to review).

**Prompt template for the agent:**

> You are an expert code reviewer focused on correctness and robustness. Review the changes on branch HEAD vs `{BASE}` in this repository.
>
> **Project standards (apply these rules):**
> {CLAUDE.md and CONTRIBUTING.md content, if they exist}
>
> **Your focus areas:**
> - Correctness: off-by-one errors, null/undefined handling, falsy value bugs (0, empty string), type coercion traps
> - Edge cases: empty arrays, missing data, concurrent access, boundary conditions
> - Data integrity: transaction boundaries for multi-step writes, race conditions, partial failure states
> - Logic duplication (within the PR): same code block repeated in multiple new files (should be extracted to a shared utility)
> - Missed reuse of existing code: new code that reimplements something that already exists in the codebase. Search for existing utilities, helpers, types, and patterns that the PR should be using instead of rolling its own. Common examples: validation logic, error classes, formatting functions, data transformation helpers.
> - Error handling: swallowed errors, missing error cases, incorrect error types at system boundaries
> - Performance: N+1 patterns, unbounded loops, unnecessary re-computation, large data in memory
>
> **How to review:**
> 1. Run `git diff {BASE}..HEAD` to see all changes
> 2. For each changed file, read the full file for context
> 3. Trace data flow through the changed code — follow function calls, check what callers expect
> 4. Pay special attention to filter/map/reduce chains and boolean conditions
> 5. Look for falsy value bugs: `if (x)` where x could legitimately be 0, empty string, or false
> 6. For any new utility, helper, constant, or pattern introduced by the PR, search the codebase for existing equivalents. Check sibling directories and files that do similar things.
>
> **Output format:**
> Return a structured list of findings. For each finding:
> - **Severity**: Critical / Major / Minor / Nit
> - **File**: exact path and line number
> - **Issue**: what's wrong, with a concrete example of how it fails
> - **Suggestion**: how to fix it
>
> Be thorough but practical. Flag real problems, not style preferences.

### Agent 3: API & Component Review

**When to include:** API routes, UI components, hooks, or form handling files changed.

**Prompt template for the agent:**

> You are an expert reviewer for APIs and UI components. Review the changes on branch HEAD vs `{BASE}` in this repository.
>
> **Project standards (apply these rules):**
> {CLAUDE.md and CONTRIBUTING.md content, if they exist}
>
> **Your focus areas:**
> - Security: auth checks on every route, input validation (Zod/schema validation, not just TypeScript types), injection risks (SQL, header, XSS), CSRF
> - API design: correct HTTP methods and status codes, proper error responses (don't leak internals), consistent patterns across routes
> - Input validation: runtime validation at system boundaries, not just TypeScript annotations. Look for routes that trust request body shape without parsing it through a schema.
> - Pattern consistency: new routes and components must follow the same patterns as existing ones in the codebase. Actively compare against sibling routes/components (e.g., if other admin routes use Zod schemas for validation, new admin routes should too — not hand-rolled `typeof` checks). Check for: auth patterns, error handling patterns, validation approach, response shapes, state management approach.
> - React patterns: unnecessary re-renders, missing cleanup in effects, stale closures, proper key usage
> - State management: derived state that should be computed, inconsistent state updates, race conditions in async state
> - Accessibility: missing ARIA labels, keyboard navigation, focus management
> - i18n: hardcoded user-facing strings that should use translation functions
>
> **How to review:**
> 1. Run `git diff {BASE}..HEAD` filtered to API and component files
> 2. For each API route, verify: auth check present AND awaited, input validated with schema, error responses use correct status codes
> 3. For each component, check: proper cleanup, no inline object/function creation in render causing re-renders, proper loading/error states
> 4. **Critically: for each new route or component, read 1-2 existing siblings** (routes in the same directory, components serving similar functions) and compare patterns. Flag deviations — the PR should match the established approach unless there's a good reason not to.
>
> **Output format:**
> Return a structured list of findings. For each finding:
> - **Severity**: Critical / Major / Minor / Nit
> - **File**: exact path and line number
> - **Issue**: what's wrong
> - **Suggestion**: how to fix it
>
> Be thorough but practical. Flag real problems, not style preferences.

### Agent 4: Test Quality & Coverage Review

**When to include:** Always (even if no test files changed — missing tests for new logic is a finding).

**Prompt template for the agent:**

> You are an expert test reviewer. Review the changes on branch HEAD vs `{BASE}` in this repository.
>
> **Project standards (apply these rules):**
> {CLAUDE.md and CONTRIBUTING.md content, if they exist}
>
> **Your focus areas:**
>
> **A. Existing test quality (for changed/new test files):**
> - Assertion depth: Do tests verify actual behavior or just that code doesn't crash? Flag tests that only assert `instanceof`, `toBeTruthy`, or `size > 0` without verifying content.
> - Edge cases: Are boundary conditions tested (empty input, null, zero, single element, max values)?
> - Test isolation: Do tests depend on execution order or shared mutable state?
> - Test data: Are builders/factories realistic? Do they cover the variations that matter?
> - Fragile assertions: Tests coupled to internal library structure, exact error message strings, or implementation details
>
> **B. Coverage gaps (for changed/new logic files):**
> - Identify new or changed functions/modules that have NO corresponding tests
> - For each untested function, assess: is it a pure function that could be easily unit tested? Or does it require integration testing?
> - Prioritize: complex logic with branching > simple getters/setters
> - Specifically look for: functions with multiple branches, sorting/filtering logic, data transformation functions, error handling paths
>
> **How to review:**
> 1. Run `git diff {BASE}..HEAD` to see all changes
> 2. For each new/changed logic file, search for corresponding test files
> 3. Read test files fully — assess whether assertions actually verify the behavior described in test names
> 4. For untested code, identify which functions are pure (extractable and testable) vs which need integration tests
>
> **Output format:**
> Return findings in two sections:
>
> **Test Quality Issues:**
> For each finding:
> - **Severity**: Critical / Major / Minor / Nit
> - **File**: exact path and line number
> - **Issue**: what's wrong with the test
> - **Suggestion**: how to improve it
>
> **Coverage Gaps:**
> For each gap:
> - **Severity**: Critical (complex untested logic) / Major (moderate untested logic) / Minor (simple untested code)
> - **File**: path to the untested code
> - **What's missing**: specific scenarios that should be tested
> - **Testability**: pure function (easy to unit test) / needs integration test / needs refactoring to be testable
>
> Be thorough but practical. Focus on tests that would actually catch bugs, not test count for its own sake.

## Phase 3: Synthesize Findings

After all agents complete, **you** (not another agent) must:

1. **Read all agent findings carefully**

2. **Deduplicate:** Multiple agents may flag the same issue from different angles (e.g., the correctness agent finds a falsy bug, the test agent finds the missing test for it). Merge these into a single finding that references both perspectives.

3. **Cross-reference:** Look for connections between findings. For example:
   - A schema issue + a query issue that compound into a bigger problem
   - A missing validation + a missing test = higher risk
   - A logic bug + duplicated logic = the bug exists in two places

4. **Re-assess severity** based on the full picture:
   - A "Minor" from one agent might become "Major" when combined with a related finding
   - A "Major" might become "Minor" if another agent found a mitigating factor

5. **Organize into the final report**

## Final Report Format

Present the synthesized review to the user:

```
## PR Review: [branch-name] ([N] commits, [M] files changed)

### Critical ([count])
Issues that will cause bugs, data loss, or security problems.
[For each: file:line, description, concrete fix suggestion]

### Major ([count])
Issues that should be fixed before merge — correctness, missing validation, logic problems.
[For each: file:line, description, concrete fix suggestion]

### Minor ([count])  
Issues worth fixing but not blocking — code quality, minor inconsistencies, hardcoded strings.
[For each: file:line, description]

### Test Coverage Gaps
[List of untested code with testability assessment]

### Nits ([count])
Style and naming suggestions. Take or leave.
[Brief list]
```

End with a **recommendation**: what to fix first and why.

## Notes

- Each agent reads the actual code, not just the diff — this catches issues where changed code interacts with existing code
- Agents read CLAUDE.md and CONTRIBUTING.md to enforce project-specific rules, not just generic best practices
- The synthesis step is critical — it's where cross-cutting concerns and compound issues are caught
- This skill does NOT run builds, linters, or tests — use `/pre-pr` for that
- This skill does NOT comment on PRs or take any public action — it reports findings to you in the terminal
