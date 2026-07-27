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

## Phase 1.5: Learn the Codebase's Conventions

Before launching agents, spend one short pass learning how *this* codebase does things, so agents can judge "does the PR fit here" rather than generic best-practice. Produce a **conventions brief** (a sentence or two per topic) and pass it verbatim to every agent alongside CLAUDE.md. Discover by grepping/reading — never guess:

- **Validation library:** does the repo use a schema validator? `grep -rlE "from 'zod'|from \"zod\"" src` (or yup/valibot). If it does, hand-rolled `typeof`/manual type-guards on untrusted input in new code is a fit violation, not a style preference.
- **Type derivation:** how are types built from their sources — Prisma `GetPayload`/`satisfies`, `Pick`/`Omit`/`extends`? A new inline type that re-spells an existing shape violates the pattern.
- **Dominant naming:** sample existing identifiers in the touched area. Note abbreviation-vs-full-word and casing conventions so new names can be checked against them (e.g. is it `Municipality*` everywhere but `Muni*` in two new spots?).
- **Shared primitives inventory:** list the existing shared components/hooks/helpers/formatters in and near the touched directories (`src/components/*`, `src/lib/utils`, `src/lib/formatters`, sibling files). **This inventory is load-bearing** — an agent cannot flag "reinvents `CityAvatar`" without knowing `CityAvatar` exists. Give the reuse agent this list explicitly.
- **Component/state patterns:** how do sibling components fetch data, hold state, and structure effects?

The brief is the difference between "looks fine" and "this doesn't match how the repo does X."

## Phase 2: Launch Specialized Review Agents

Launch **all applicable agents in parallel** using a single message with multiple Agent tool calls. Each agent gets the full diff for its domain plus the project standards.

Skip agents whose domain has no changed files (e.g., skip the schema agent if no schema files changed).

**Evidence over conclusions (applies to every agent).** For any "is there an existing X?" / "does this follow the pattern?" check, the agent MUST show its work — the grep it ran, the sibling it compared against, and what it found — and only then conclude. A bare "no missed reuse" or "follows conventions" with no shown search is **not acceptable**: that exact hand-wave is how real issues slip through (an agent once reported "Missed Reuse: Clean" while an existing avatar component sat unreused). If an agent can't cite the search, it hasn't done the check — treat that section as unreviewed.

### Agent 1: Data Layer & Schema Review

**When to include:** Schema files, migrations, seed files, ORM config, database query files, or API routes changed.

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
> - Type derivation: types that represent DB query results should be derived from the ORM (e.g. Prisma's `satisfies` + `GetPayload` pattern), not manually defined as `Type & { ... }`. Manual type definitions drift when the schema or query changes.
> - CRUD boilerplate: when the input type already matches the ORM's expected shape, data should be passed directly — not destructured and reassembled field-by-field. Manual field mapping is a maintenance burden and a source of bugs when fields are added.
> - Data layer bypass: API routes and components must use existing data access functions (e.g. from `lib/db/`) rather than writing inline ORM queries. Inline queries bypass shared logic (filtering, authorization, defaults) and create maintenance duplication.
> - Duplicate query functions: check if a new query function duplicates or nearly duplicates an existing one. If two functions do the same thing with minor differences (e.g. one filters deprecated records, the other doesn't), they should be consolidated.
>
> **How to review:**
> 1. Run `git diff {BASE}..HEAD` filtered to relevant files to see the changes
> 2. For each changed file, also read the full file for context (not just the diff)
> 3. When reviewing queries, check if the fields being queried have appropriate indexes
> 4. For migrations, verify they are safe to run on a production database with data
> 5. For any new type definition that represents a DB result, check if it could be derived from the ORM instead
> 6. For any new API route with a DB query, check if an equivalent function already exists in the data access layer
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
> - Type consistency: when an interface or type alias is defined, check that all functions producing or consuming that shape actually reference it rather than defining the same shape inline. Look for return type annotations like `Promise<{ success: boolean; error?: string; ... }>` repeated across multiple functions — these should use a shared named type. Also check for near-duplicate type definitions (same fields minus one or two) that should use `extends`, `Pick`, or `Omit` to express the relationship. Inline types that repeat the same shape drift silently when one is updated but the others aren't.
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
> 7. For type consistency: collect all inline return types and parameter types across the PR's changed files. Group by shape similarity. If two or more functions define the same or near-identical shape inline, flag it — there should be a single named interface. If a named interface already exists but functions don't reference it, flag that too.
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
> - Hardcoded data that duplicates DB fields: watch for static maps, constants, or switch statements that replicate data already stored in the database (e.g. a hardcoded icon-per-category map when the DB model has an `icon` field). These drift silently when the DB is updated. The component should read the value from the data it already has.
> - Duplicate components: if a new component is structurally similar to an existing one (same data shape, similar rendering, similar interactions), flag it. They should be consolidated into a single reusable component with props for the differences.
> - React patterns: unnecessary re-renders, missing cleanup in effects, stale closures, proper key usage
> - State management: derived state that should be computed, inconsistent state updates, race conditions in async state
> - Controlled vs uncontrolled: components that fetch their own data AND manage selection state internally are hard to reuse. Prefer controlled components (receive data + state from parent, report changes via callbacks) with shared hooks for data fetching.
> - Accessibility: missing ARIA labels, keyboard navigation, focus management
> - i18n: hardcoded user-facing strings that should use translation functions
>
> **How to review:**
> 1. Run `git diff {BASE}..HEAD` filtered to API and component files
> 2. For each API route, verify: auth check present AND awaited, input validated with schema, error responses use correct status codes
> 3. For each component, check: proper cleanup, no inline object/function creation in render causing re-renders, proper loading/error states
> 4. **Critically: for each new route or component, read 1-2 existing siblings** (routes in the same directory, components serving similar functions) and compare patterns. Flag deviations — the PR should match the established approach unless there's a good reason not to.
> 5. For components that render entity-specific data (icons, colors, labels), verify they read from the data model rather than hardcoding a mapping. Search for static maps or constants that mirror DB fields.
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

### Agent 5: Reuse & Codebase-Fit Review

**When to include:** Always.

**Prompt template for the agent:**

> You are a reviewer for **reuse and codebase-fit**: does the PR use what already exists and follow how *this* repo does things, rather than reinventing or diverging? This is the check that most often produces a false "looks clean," so it is procedure-driven and evidence-required.
>
> **Conventions brief (from Phase 1.5):**
> {conventions brief, including the shared-primitives inventory}
>
> **Project standards:**
> {CLAUDE.md and CONTRIBUTING.md content}
>
> **Mandatory procedure — produce the evidence, do not skip or summarize:**
> 1. **Enumerate every new exported symbol** the PR adds — components, hooks, helpers, types, constants. List them explicitly.
> 2. **For each, search the codebase for a pre-existing equivalent** by name *and* by function — grep by likely names and by the concept (e.g. a new logo-with-fallback component → `grep -riE "avatar|logoImage" src/components`). **Paste the grep(s) and the candidates you found.** You may conclude "no existing equivalent" ONLY with the searches shown. An unsupported "clean" is a failed review.
> 3. **Fit checks against the brief:**
>    - Untrusted-input validation hand-rolled where the repo uses a schema library (Zod)?
>    - A new inline type re-spelling an existing shape instead of `Pick`/`Omit`/derivation?
>    - New names against the dominant naming convention (abbreviation vs full word, casing)?
>    - A helper hand-rolled inline (viewport/geometry/date/formatting/etc.) that already exists?
> 4. **Duplication within the PR:** the same block or type shape repeated across 2+ new files.
>
> **Output format:** Severity (Critical/Major/Minor/Nit) / File:line / Issue — **naming the existing thing it should use, with its path** / Suggestion. Reuse and fit findings are first-class even when they are "Minor" severity — they are the maintenance cost the codebase carries. Do not fabricate; but do not conclude "clean" without the searches above.

### Agent 6: Simplicity & Patch-Smell Review

**When to include:** Always.

**Prompt template for the agent:**

> You are a reviewer for **simplicity and design**: did the PR solve the problem *well*, or bolt complexity on / patch a symptom? "Robust and well-tested" is NOT the bar you enforce — a module can be robust, tested, and still over-built or modeled wrong. Your bar is "as simple as the problem allows, and modeled the right way for the framework."
>
> **Conventions brief (from Phase 1.5):**
> {conventions brief}
>
> **Look for (and for each, give a concrete simpler alternative — argue the case, don't just assert):**
> - **Over-engineering / YAGNI:** speculative generality, config/params for a single caller, guards for cases that cannot occur (e.g. a read that accepts values the write can never produce), asymmetries that carry an explanatory comment justifying a hypothetical future. Ask "what actually breaks if this were simpler?"
> - **State written by effects that should be derived or event-driven:** `useEffect` + `setState` computing a value a `useMemo`/render expression could; state that mirrors a prop; the same piece of state written from several effects (or effects + imperative handlers) with precedence that depends on flush order.
> - **Refs as escape hatches:** the "adjust state when a prop changes, via a previous-value ref" anti-pattern; refs used to dodge a dependency array where a `useCallback`/`useMemo` is the real fix. Distinguish the *justified* case — callbacks/values read inside long-lived listeners (Mapbox, subscriptions) that must not re-subscribe — and leave those alone.
> - **`eslint-disable react-hooks/exhaustive-deps`:** for each occurrence, judge whether it hides a design that fights React or is a legitimate run-once / only-on-X.
> - **Additive branching / god-objects:** a props or params object where many fields are dead for one caller; long if/else ladders bolted on over time; booleans that could collapse; the same value passed under two different names.
> - **Comment hygiene:** comments restating what the code plainly says; the same rationale copy-pasted at every call site instead of stated once at its root (call sites should point to it, not repeat it).
>
> **How to review:** read the changed files fully and trace how state/data flows rather than reading lines in isolation — patch-smells show up in the *shape* of the flow, not a single line. Separate genuine smells from justified patterns (imperative glue at a framework boundary is often unavoidable; say so, and don't cry wolf on it).
>
> **Output format:** Severity / File:line / Issue (name the construct and *why* it reads as patched-together or over-built) / Suggestion (the simpler model). These are judgment findings — a reader who doesn't know the code should be able to follow your argument.

## Phase 3: Synthesize Findings

After all agents complete, **you** (not another agent) must:

1. **Read all agent findings carefully**

2. **Deduplicate:** Multiple agents may flag the same issue from different angles (e.g., the correctness agent finds a falsy bug, the test agent finds the missing test for it). Merge these into a single finding that references both perspectives.

3. **Cross-reference:** Look for connections between findings. For example:
   - A schema issue + a query issue that compound into a bigger problem
   - A missing validation + a missing test = higher risk
   - A logic bug + duplicated logic = the bug exists in two places

4. **Verify Major and Critical findings:** For any finding rated Major or Critical, read the relevant code yourself before including it in the report. Agent findings are hypotheses, not facts — agents may misunderstand framework behavior, miss context from files they didn't read, or make wrong assumptions. If you can't confirm the issue by reading the code, downgrade or drop it.

5. **Re-assess severity** based on the full picture:
   - A "Minor" from one agent might become "Major" when combined with a related finding
   - A "Major" might become "Minor" if another agent found a mitigating factor

6. **Keep maintainability findings first-class.** Reuse, codebase-fit, simplicity, naming, and comment findings are usually low *severity* (they rarely crash anything) but high *value* — they are exactly what an experienced maintainer catches and a correctness-only pass misses. Don't bury them as "nits"; give them their own section (below). Also **confirm the reuse/fit agent actually showed its searches** — if it concluded "clean" without pasting greps, treat that as unreviewed and verify it yourself.

7. **Organize into the final report**

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

### Maintainability & Fit
Reuse misses (reinvents existing code — name it), convention divergences (validation / type-derivation / naming), over-engineering and patch-smells (state-via-effects, escape-hatch refs, god-object props, YAGNI), and comment/naming hygiene. Low severity, high value — the experienced-maintainer layer a correctness-only pass misses.
[For each: file:line, what it reinvents / diverges from / over-builds, and the simpler or shared alternative]

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
- **Phase 1.5 (convention discovery) is what makes "does this fit?" answerable** — without the shared-primitives inventory and the validation/type/naming conventions, agents fall back to generic best-practice and miss codebase-specific divergences
- **"Evidence over conclusions" is the load-bearing rule.** The reuse and fit checks already existed as agent instructions before this — and agents hand-waved them ("no missed reuse" while an existing component sat unreused). Requiring the shown grep is what closes that gap; adding more lenses without it just produces more confident hand-waving
- The synthesis step is critical — it's where cross-cutting concerns and compound issues are caught
- This skill does NOT run builds, linters, or tests — use `/pre-pr` for that
- This skill does NOT comment on PRs or take any public action — it reports findings to you in the terminal
