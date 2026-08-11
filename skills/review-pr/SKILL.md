---
description: "Deep PR review using parallel specialized agents, with optional runtime/visual verification and evidence-backed review posting. Use before merging to catch real issues."
argument-hint: "[pr-number | base-branch]"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Edit", "Write", "Agent"]
---

# Deep PR Review

Run a thorough pull request review using parallel domain-specialized agents, each bringing deep expertise to a different aspect of the code. This is not a linter — it catches the issues that only an experienced reviewer would find.

**Argument:** $ARGUMENTS — a **PR number** (e.g. `218`), a **base branch** (e.g. `develop`), or empty. Phase 0 resolves which. When it resolves to a GitHub PR, the review is grounded in that PR's history (description, linked issues, prior reviews) so it doesn't re-litigate settled points. Default base branch: auto-detect from `main` or `master`.

## Phase 0: Resolve Target & Fetch PR/Issue Context

**Runs first whenever the review targets a GitHub PR.** This is what keeps the review from re-litigating points already raised, missing the acceptance criteria the diff is supposed to satisfy, and presenting a months-old open blocker as a fresh discovery. If the review is a local-branch-only review with no associated PR, skip this phase and note in the final report that the review is **diff-only** (no history to reconcile against).

### 0a. Interpret the argument and resolve the PR

**The normal case: you run this from inside the review worktree with the PR branch already checked out**, so local `HEAD` *is* the PR tip and Phases 1–2 review `HEAD` unchanged. Phase 0's job is then only to **identify which PR `HEAD` belongs to** and fetch its context — no re-checkout, no new worktree.

`$ARGUMENTS` may be a PR number, a base branch, or empty:
- **Empty** (most common) → resolve the PR for the current branch: `gh pr view --json number,baseRefName,url,reviewDecision`. Set `BASE = upstream/<baseRefName>` (or the existing auto-detected base). Fetch its context (0b). If no PR is associated, degrade to **diff-only**.
- **Non-numeric** → a **base branch** override (existing behavior). Still run `gh pr view --json number 2>/dev/null` for the current branch and fetch context if a PR exists.
- **All digits** (e.g. `218`) → a **PR number**. If it matches the PR already checked out at `HEAD`, treat as the empty case. **Only if `HEAD` is not that PR** (running off-workflow from an unrelated branch) fall back to fetching the PR into a throwaway worktree so the diff is correct:
  ```bash
  gh pr view <PR#> --json headRefName,baseRefName,headRefOid,state,url,reviewDecision
  git fetch upstream pull/<PR#>/head && git fetch upstream <baseRefName>
  git worktree add /tmp/review-pr-<PR#> --detach FETCH_HEAD   # review here; BASE = upstream/<baseRefName>
  ```
  Clean the worktree up at the end. This branch is the exception, not the default — don't create a worktree when `HEAD` is already the PR tip.

### 0b. Fetch the history — then distill, don't dump

```bash
gh pr view <PR#> --json title,body,author,labels,closingIssuesReferences,reviewDecision
gh pr view <PR#> --json reviews --jq '.reviews[] | "[\(.submittedAt)] \(.author.login) (\(.state)): \(.body)"'
gh api repos/<owner>/<repo>/pulls/<PR#>/comments --paginate \
  --jq '.[] | "[\(.created_at)] \(.user.login) @ \(.path):\(.line // .original_line)\n\(.body)"'   # inline line-level
gh api repos/<owner>/<repo>/issues/<PR#>/comments --paginate \
  --jq '.[] | "[\(.created_at)] \(.user.login): \(.body)"'                                          # conversation
gh pr checks <PR#> 2>/dev/null || true                                                              # CI state
```
For each **linked issue** in `closingIssuesReferences` (and any `Closes #N` / `Fixes #N` in the body), fetch it:
```bash
gh issue view <n> --json title,body
```
Watch for **bot summaries** in the PR body and reviews (Greptile, Cursor, CodeRabbit): they often carry a confidence score and a cited blocker on the *current* head — that is a standing finding, not to be re-discovered.

### 0c. Produce three artifacts — passed verbatim to every agent (like the conventions brief)

1. **Acceptance criteria** — what the PR must actually do, distilled from the PR description **and** the linked issues. Agents check the diff *against* this, not just for generic defects. A stated goal the diff silently fails to meet, or an explicit maintainer note (e.g. *"automated tests were intentionally skipped"*), is a **first-class finding**.
2. **Resolved ledger** — points raised in prior human/bot review that the author has **since addressed**. Agents must **NOT** re-raise these. Spot-check a sample against the current diff — a reviewer may have asked for X and the author only did it partially (that partial gap *is* still a finding).
3. **Standing ledger** — points raised in prior review that are **still unaddressed** on the current head: unresolved maintainer comments and live bot blockers (with the reviewer + file cited). The review should **confirm and surface these as standing** (attributed to who first raised them), not dress them up as new discoveries.

Also note the **reviewers already involved** (human vs bots) and the PR's `reviewDecision` — this calibrates tone and how much is worth repeating. The three ledgers flow into Phase 2 (agents avoid resolved items, hunt against acceptance criteria) and Phase 4 (each finding is reconciled against them).

## Phase 1: Scope, Standards & Conventions

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

5. **Make the checkout runnable.** Check whether the project's dependencies actually resolve (`node_modules` present *and* containing the packages the diff imports — a stale tree is worse than an absent one, because it fails late). If they don't, install them now. This is a two-minute step that decides how much of the review is code-reading and how much is evidence: with a runnable checkout, agents can run the type-checker and the suite, and Phase 3 can mutation-test a proposed test. Tell every agent explicitly what it *can* execute — an agent told "you cannot run tests" will not try.

6. **Read the third-party behaviour the diff leans on.** If the PR's correctness depends on how a library or framework behaves — lifecycle and instantiation, caching, ordering, how many times something is invoked, what a wrapper passes its callback — find that behaviour in the package's own source and read it. `npm pack <pkg>@<range> && tar xzf` gets you the published dist when the package isn't installed. Note what you confirmed; it goes to the agents as fact, and it is the one class of assumption they cannot check for themselves.

### Learn the codebase's conventions

Then spend one short pass learning how *this* codebase does things, so agents can judge "does the PR fit here" rather than generic best-practice. Produce a **conventions brief** (a sentence or two per topic) and pass it verbatim to every agent alongside CLAUDE.md. Discover by grepping/reading — never guess:

- **Validation library:** does the repo use a schema validator? `grep -rlE "from 'zod'|from \"zod\"" src` (or yup/valibot). If it does, hand-rolled `typeof`/manual type-guards on untrusted input in new code is a fit violation, not a style preference.
- **Type derivation:** how are types built from their sources — Prisma `GetPayload`/`satisfies`, `Pick`/`Omit`/`extends`? A new inline type that re-spells an existing shape violates the pattern.
- **Dominant naming:** sample existing identifiers in the touched area. Note abbreviation-vs-full-word and casing conventions so new names can be checked against them (e.g. is it `Municipality*` everywhere but `Muni*` in two new spots?).
- **Shared primitives inventory:** list the existing shared components/hooks/helpers/formatters in and near the touched directories (`src/components/*`, `src/lib/utils`, `src/lib/formatters`, sibling files). **This inventory is load-bearing** — an agent cannot flag "reinvents `CityAvatar`" without knowing `CityAvatar` exists. Give the reuse agent this list explicitly.
- **Component/state patterns:** how do sibling components fetch data, hold state, and structure effects?

The brief is the difference between "looks fine" and "this doesn't match how the repo does X."

## Phase 2: Launch Specialized Review Agents

Launch **all applicable agents in parallel** using a single message with multiple Agent tool calls. Each agent gets the full diff for its domain plus the project standards.

**Pass the Phase 0 artifacts to every agent** (when the review targets a PR): the **acceptance criteria** (so agents also check the diff *satisfies the PR's stated goals and linked issues*, not just that it's defect-free) and the **resolved ledger** with the instruction: *"These points were already raised and addressed in prior review — do not re-raise them; if you believe one was only partially addressed, say so explicitly and show the gap."* Do **not** feed agents the standing ledger as their own findings — that stays with you for reconciliation in Phase 4, so agents rediscover independently (a genuine independent hit corroborates the standing item; silence doesn't erase it).

Skip **Track A** agents whose domain has no changed files (e.g. skip the schema agent if no schema files changed). **Track B is not skippable on that basis** — its domain isn't a file type, it's the delta itself, so "no files in my area" never applies. Drop it only for documentation, config, or a refactor that touches no conditional at all.

**Match the evidence to the claim (applies to every agent, and to you).** A claim is discharged only by the right *kind* of evidence, and each kind is cheap to state:

| Claim | What discharges it |
|---|---|
| "X already exists" / "this follows the pattern" | the search you ran, and what it returned |
| "X is broken" | concrete inputs → the wrong output |
| **"X changed"** | **the before and the after, observed** (`git show {BASE}:path`, or two running builds) |
| **"X is severe"** | **a measurement** — fraction of the surface, pixels, ms, rows |
| **"the library/framework does X"** | **that package's source, read** — not its docs, and never a comment in the diff asserting it |
| **"this test catches Y"** | **Y introduced, and the test observed failing** |

A bare "no missed reuse" or "follows conventions" with no shown search is **not acceptable** — that exact hand-wave is how real issues slip through (an agent once reported "Missed Reuse: Clean" while an existing avatar component sat unreused). If an agent can't cite the search, it hasn't done the check: treat that section as unreviewed.

The bottom two rows are the ones that get skipped. **Evidence of reading is not evidence of behaviour.** An agent can quote the exact line that removed a feature and file it as a style nit, because "this line is untidy" and "this line turned something off for users" are different claims needing different evidence.

**Describe the symptom, not the unit.** When briefing an agent on something you have half-spotted, give it the symptom and make it establish the scope itself — "the PR adds fields to several response mappers; establish how many exist and what they share" — not "these three fields appear at four sites, should there be a helper?". An agent handed a unit investigates that unit and reports on that unit. Naming the boundary is how you get a correct answer to the wrong question.

**Keep each command short, even though the checkout is runnable.** An agent parked in one long command — a full build, the whole suite, an install — can be killed for inactivity and return *nothing*. When you tell agents what they may execute (Phase 1, step 5), scope it: a targeted test file rather than the suite, `tsc --noEmit` rather than the build, and abandon anything running past a couple of minutes rather than waiting it out. Whatever genuinely needs the long command is yours in Phase 3, or `/pre-pr`'s.

Agents run in **two tracks**, launched together. **Track A** asks whether the code is good. **Track B** asks what the running product does differently. Both are needed: a PR is not a body of code that arrived, it is a transition from state A to state B, and Track A only ever sees state B.

---

## Track A — code quality

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
> - Logic duplication: the same code block repeated across new files, **or repeated between new code and pre-existing siblings** — count the instances, including the ones outside the diff, and extract to a shared utility
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
> 5. **Check what actually blocks a test before calling something untestable.** Type-only imports erase at compile time, so a module that "depends on the SDK" may need none of it at runtime; a transitive import of the ORM is usually one `jest.mock` away. Follow the import chain and name the real obstacle, or say there isn't one — "needs an integration test" is a claim, and it is wrong more often than it is right.
>
> **If the suite is runnable, mutation-test every test you propose.** Write it, run it (it must pass), then introduce each bug you claim it catches — one at a time — and confirm it fails. Report a table: mutation → result. This is not ceremony: it routinely changes the test's *design*, because it exposes assertions that are structurally blind to the regression they were written for. A proposed test with no mutation table is a sketch, and should be labelled one.
>
> Prefer assertions on the **difference** between two states over a full inventory snapshot, when the property under test is a difference (e.g. "the authenticated tool list minus the anonymous one is exactly this set"). Inventory assertions force an edit every time something unrelated is added, so they get deleted; difference assertions survive.
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
> **Conventions brief (from Phase 1):**
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
> 4. **Duplication — count the instances first, then derive the unit.** For every block the PR adds, including **inline object literals and returned shapes** (not just exported symbols), grep the touched file *and its siblings* for structurally similar blocks that already exist. A PR adding the *first* copy of something is rare; the usual case is a PR adding the **Nth** copy of a shape already present N−1 times — which looks clean in the diff, because the diff holds exactly one instance. Report the count and where the others live.
>    Then **derive the unit before proposing a fix**: diff two full instances field by field and report the largest region they share, not the part that first caught your eye. If this prompt named specific fields or lines, treat that as a starting point, never a boundary.
> 5. **Sibling output contracts.** If the PR touches anything emitting a record to an external consumer — an API route, an MCP tool, a serializer — enumerate every sibling emitting the *same kind* of record and diff their emitted shapes field by field. Divergence in field names, nullability, date/number formatting, or where a field sits in the envelope is a first-class finding: one contract defined in several places that has already drifted. Consumers see the inconsistency even when each site is individually correct.
>
> **Output format:** Severity (Critical/Major/Minor/Nit) / File:line / Issue — **naming the existing thing it should use, with its path** / Suggestion. Reuse and fit findings are first-class even when they are "Minor" severity — they are the maintenance cost the codebase carries. Do not fabricate; but do not conclude "clean" without the searches above.

### Agent 6: Simplicity & Patch-Smell Review

**When to include:** Always.

**Prompt template for the agent:**

> You are a reviewer for **simplicity and design**: did the PR solve the problem *well*, or bolt complexity on / patch a symptom? "Robust and well-tested" is NOT the bar you enforce — a module can be robust, tested, and still over-built or modeled wrong. Your bar is "as simple as the problem allows, and modeled the right way for the framework."
>
> **Conventions brief (from Phase 1):**
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

---

## Track B — behaviour delta

### Agent 7: Behaviour-Delta Review

**When to include:** any diff that changes rendering, fetching, routing, enabling, or thresholds — in practice, almost all application code. Skip only for pure documentation, config, or a refactor that touches no conditional.

**Prompt template for the agent:**

> You are the **behaviour-delta reviewer**. Every other agent asks whether the code is good. You ask exactly one question: **what does the running product do differently after this change, and was each difference intended?**
>
> A PR is a transition from state A (the base) to state B (this branch). Three questions follow, and the other agents only cover the first:
> 1. What does B do that A didn't? — new capability.
> 2. **What did A do that B doesn't?** — removed behaviour.
> 3. **What do both do, differently?** — changed behaviour.
>
> Questions 2 and 3 are yours, and they are where silent regressions live: the author tested the feature they were building, not the flows that already ran through the code they changed.
>
> **Project standards and conventions brief:** {CLAUDE.md, CONTRIBUTING.md, conventions brief}
> **Acceptance criteria:** {Phase 0 artifact — this is how you judge "intended"}
>
> **Mechanically findable change sites — start here, they are greppable:**
> - A boolean gating render or execution that **gained or lost a term**. `active: X` → `active: X && !Y` means "in state Y, this no longer happens". Search the diff for added `&&`/`||` on anything named `active|enabled|disabled|visible|show*|is*|has*|can*|should*`.
> - **Dependency arrays that lost an entry** — that removes a re-run, and whatever used to happen on that re-run stops happening.
> - Added early returns and guard clauses.
> - Changed defaults, thresholds, constants, enum/union members.
> - `if`/`switch` conditions whose shape changed.
> - Props removed from, or renamed on, an existing component.
>
> **For each site, produce a row:**
>
> | state | before (base) | after (this branch) | intended? |
>
> Write before/after in **user-visible terms, not code terms**. "On the municipalities tab, subject pins used to render past zoom 9; now they never render" — *not* "the active prop gained a term". If you cannot say what a user would see, say so: that row becomes a runtime check rather than a finding.
>
> **Judging "intended":** check the PR description, commit messages, and linked issues. A described change is intended. **A change that is a side effect of a described change is the most valuable finding you can produce** — the author swapped a layer deliberately and did not notice that an existing action depended on it. Say which of the two you're looking at.
>
> **Method:** for every site you flag, read the **base** version of the file (`git show {BASE}:path`), not just the diff. The diff shows the line that changed; only the base file shows what that line used to permit.
>
> **Output:** the table, plus — for every row answered "no" or "unclear" — the exact user steps that would reveal the difference, written so someone else can execute them without reading the code. That list is the runtime test matrix for Phase 3.

## Phase 3: Runtime Verification

**Default ON** when both hold: the change touches user-visible behaviour, *and* the app can be run (a PR preview, a staging deploy, or a local dev server). Skip only when neither holds — and when you skip, **say so in the report, with the reason**. An unrun review is a weaker review, and the reader is entitled to know which one they're getting.

Drive it with the **browser-scripting** skill. `references/runtime-probes.md` carries the probe patterns and the gotchas that silently invalidate results.

First, **discover run/auth conventions from the project's own docs** (`CLAUDE.md`, `CONTRIBUTING.md`, project skills): how to start the app, how to authenticate as the role the change needs, and which environment is safe to write to. Never write to a production database. If it isn't documented, ask.

Then **actually obtain the credential, before you run anything.** Discovering that a dev-login route or a seed script exists is not the same as having a session, and the gap between them is where Phase 3 quietly degrades into a half-review. When a change is auth- or role-gated, the gated side is the side the author exercised least and the side no anonymous probe can reach — so it is exactly where your marginal value is highest, and exactly what gets left as inference when the credential looks like a ten-minute detour. Budget the ten minutes. If you genuinely cannot get one, that is a "could not reach" row in 3b and a stated limit in 3h, never a silent omission.

**Write the code and data the reproduction needs — that is the job, not a detour.** Seed the records the repro requires rather than hunting for a case that happens to exist; inject instrumentation into the running page (see *Instrumenting the page* in `references/runtime-probes.md`). The difference between "I think this is a bug" and a measurement is almost always a piece of throwaway probe code. Production stays off-limits; dev and local databases are yours. On a **shared** staging or preview database, prefer probes that can't persist — pick the code path that doesn't write (a no-op save branch, cancel instead of confirm) — and say in the report that the probe was non-destructive.

This phase does two jobs, in this order: the first **discovers** what no agent proposed, the second **confirms and sizes** what they did.

### 3a. Baseline A/B — do this first

**Single-sided testing only finds the bugs you thought to look for. Diffing two deployments finds the ones nobody thought about.**

If the base is deployed anywhere (production, staging, a `main` preview), write **one** script that drives the *same steps* against both it and the PR build, dumping a structured inventory of observable state at each step — rendered elements grouped by kind, visible text, open dialogs, URL, network calls — and diff the two inventories.

Choose the steps from **existing user flows that pass through changed code**, not from the new feature. The new feature has no baseline to differ from; the existing flows do, and that is exactly where a silent regression hides. Include one step you expect to be identical, as a control on your own classifier.

Any difference the PR description doesn't account for is a finding.

**The two sides must be comparable in the ways the probe depends on**, and a deployed baseline often isn't. Environments differ in what they permit: a staging deploy may refuse the dev-login route that previews allow, so the gated surface you need is unreachable on that side even though the page loads. Check that the baseline can reach the same state — authenticate, same data, same feature flags — before trusting a diff against it, and fall back to running the base locally on a second port or in a second worktree when it can't.

### 3b. Execute the behaviour matrix

Track B produced a table of states where behaviour may differ, each with the user steps that would show it. Drive them. Every row resolves to **confirmed**, **not reproduced**, or **could not reach** — and "could not reach" goes into the report as exactly that, never as silence.

**Before believing a "not reproduced", prove the probe actually reached the condition.** A probe that never triggers the mechanism returns "identical on both builds" — which reads exactly like "no regression" and is the most dangerous result this phase can produce, because it retires a true hypothesis with apparent evidence. So assert the **precondition** as its own observable, not just the outcome: if the finding depends on a re-render, assert that state actually changed; if it depends on a request, assert it fired; if it depends on scroll, assert the position moved. Print that assertion next to the result. When a negative depends on a precondition you did not verify, it is "could not reach", not "not reproduced".

This is a different control from the classifier control in 3a: that one guards against your *measurement* being wrong, this one guards against your *setup* being inert.

### 3c. Measure, don't estimate

Before any finding keeps a Major or Critical rating, get a **number**: what fraction of the surface is affected, how many pixels, how many milliseconds, how many rows. Severity assigned from reading code is a guess, and guesses run high. A defect can be entirely real and still be a nit.

### 3d. Map every entry point

When the change touches a **shared** component / util / hook, grep for *all* its call sites and split them into **fix-target** (where the change is aimed) and **regression** (other consumers it could break). Exercise each. A single path is not coverage — the author typically checked the one surface they were focused on, and this is where the review adds coverage.

Also ask **"what's missing?"** — files that should have changed and didn't: call sites not updated, the symmetric path not handled (error handling added to `createX` but not `deleteX`).

### 3e. Check the viewports that matter

UI diverges across breakpoints. Default set (`newContext({ viewport })`): **mobile 390×844**, **tablet 768×1024**, **desktop 1440×900**. Scope by relevance — a pure API/data change needs none. Derive the project's *own* breakpoints from its config (e.g. Tailwind `theme.screens`) and take a just-below / just-above pair, since the layout switches at the boundary. **Read the project's media queries rather than assuming**: a width you'd call "tablet" may resolve to the mobile layout.

### 3f. Capture artifacts as you go

Screenshot or record **every finding that reproduces, at the moment it reproduces** — never plan to reproduce it later for the picture. The artifacts are for the PR author: a console table proves it to you, an image proves it to them. Prefer an A/B pair with a working control when the defect is an asymmetry, annotate geometric defects before capturing, and record video for interaction defects a still can't show. Check the artifact actually shows the defect before you use it.

**Make the artifact self-evident.** A raw screenshot of a complex app proves nothing to someone who wasn't driving it — they can't see which element you meant, what the state was, or which step they're looking at. Build the explanation into the page *before* capturing: highlight the element under test, show the live state the claim is about, caption the current step. Then a still carries its own argument and a video narrates itself.

**Put them where the reader can open them, and link them.** Write artifacts to a stable directory outside any session scratchpad — `~/<pr-or-topic>-evidence/` — and in the report **link every one as a clickable `file:///absolute/path`**, with a one-line statement of what it shows. Artifacts that exist but are never surfaced did not happen: the reader's ability to check your work themselves is most of their value, and these are the same files that get uploaded in Phase 6.

### 3g. Prove the tests you recommend

A recommended test is a finding like any other, and "this test would catch the regression" is a claim needing its matching evidence. If Agent 4 could not run the suite, you do it here: write the test, watch it pass, then introduce each bug it claims to catch and watch it fail. Report the mutation table alongside it.

Expect this to change the test, not merely bless it — an assertion can be entirely correct and still structurally blind to the exact mistake it was written to prevent, and only the mutation reveals which. Recommending an unmutated test is how a review hands the author busywork with a confident face.

### 3h. Report honestly

State what you **verified** versus what you **inferred**, and at which viewports. A path you couldn't reach is inference — say so, and never let an untested path read as covered. Name the sides you exercised: "verified anonymous, inferred authenticated" is an honest and useful sentence; silence about the second half is not.

**Report the hypotheses measurement killed, not just the ones it confirmed.** A predicted defect that the A/B shows to be identical on both builds is a real result and belongs in the report — it tells the author which scary-looking part of their diff is actually inert, and it is the clearest evidence that the review's severities came from observation rather than from reading. Say what you expected, what you measured, and that you dropped it.

## Phase 4: Synthesize Findings

After all agents complete and the runtime results are in, **you** (not another agent) must:

1. **Read all agent findings carefully**

2. **Deduplicate:** Multiple agents may flag the same issue from different angles (e.g., the correctness agent finds a falsy bug, the test agent finds the missing test for it). Merge these into a single finding that references both perspectives.

3. **Cross-reference:** Look for connections between findings. For example:
   - A schema issue + a query issue that compound into a bigger problem
   - A missing validation + a missing test = higher risk
   - A logic bug + duplicated logic = the bug exists in two places

4. **Verify Major and Critical findings:** For any finding rated Major or Critical, read the relevant code yourself before including it in the report. Agent findings are hypotheses, not facts — agents may misunderstand framework behavior, miss context from files they didn't read, or make wrong assumptions. If you can't confirm the issue by reading the code, downgrade or drop it. The same applies to any test an agent proposes: unmutated, it is a sketch (3g), and an agent's account of *why* a test is hard to write is itself a hypothesis worth ten seconds of checking.

   **A dead agent's domain is unreviewed.** Agents stall, hit watchdogs, and die. When one does, its silence is indistinguishable from a clean report at synthesis time — the exact failure this skill spends its evidence rules preventing. Re-run it, or cover its domain yourself and say in the report which you did.

5. **Re-assess severity** based on the full picture:
   - A "Minor" from one agent might become "Major" when combined with a related finding
   - A "Major" might become "Minor" if another agent found a mitigating factor
   - **Nothing keeps a rating above Minor on code-reading alone.** Either it carries a measurement from Phase 3, or it is tagged *unmeasured* in the report so the reader can discount it. Agents rate from the shape of the code and consistently rate high; measurement is what separates a real defect from a real *and serious* one.
   - **A regression outranks a defect of the same size.** "This used to work and now doesn't" is a different claim from "this could be better", and the reader needs to see which they're getting.

6. **Keep maintainability findings first-class.** Reuse, codebase-fit, simplicity, naming, and comment findings are usually low *severity* (they rarely crash anything) but high *value* — they are exactly what an experienced maintainer catches and a correctness-only pass misses. Don't bury them as "nits"; give them their own section (below). Also **confirm the reuse/fit agent actually showed its searches** — if it concluded "clean" without pasting greps, treat that as unreviewed and verify it yourself.

7. **Reconcile against the Phase 0 ledgers** (skip if diff-only). This is what makes the review worth a maintainer's time on a PR with history — tag every finding:
   - **NEW** — not raised before. The review's real contribution; lead with these.
   - **STILL-OPEN** — matches a standing-ledger item or an independent agent hit on a live bot blocker. Keep it, but attribute it (*"first raised by @X on <date>"* / *"Greptile's current blocker"*) and present it as confirmation, not discovery.
   - **ALREADY-ADDRESSED** — matches the resolved ledger and the current diff confirms it's fixed. **Drop it** (or, if only partially fixed, keep *only* the residual gap and say so). Do not spend the reader's attention re-closing settled points.

   Then **check acceptance-criteria coverage**: for each stated goal (PR description + linked issues), does the diff actually deliver it? An unmet or partially-met criterion, or a flagged maintainer caveat (e.g. tests deliberately skipped), is a finding in its own right.

8. **Organize into the final report**

## Phase 5: Report

Present the synthesized review to the user:

When the review targets a PR, open with a one-line context header (`reviewDecision`, who has already reviewed, current bot confidence if any) and an **Acceptance criteria** check, then the severity sections. Tag each finding **[NEW]**, **[STILL-OPEN → @who]**, so the reader instantly sees what's genuinely new versus a confirmed standing item. Put confirmed-but-old items in the **Standing items** section, not mixed into the fresh findings. Omit the PR header and these two sections for a diff-only review.

Additionally tag **[REGRESSION]** on anything that worked before this branch and doesn't now, and **[unmeasured]** on anything rated above Minor without a Phase 3 measurement behind it. A reader triaging a long review needs to see, at a glance, which items are "this got worse" and which are "I think this is bad but didn't check."

```
## PR Review: [branch-name] ([N] commits, [M] files changed)
[PR #N — reviewDecision · already reviewed by @a, @bot (conf X/5) · closes #issue]   ← PR reviews only

### Acceptance criteria (PR reviews only)
[Each stated goal from PR body + linked issues → met / partially-met (gap) / unmet. Flag maintainer caveats.]

### Critical ([count])
Issues that will cause bugs, data loss, or security problems.
[For each: [NEW]/[STILL-OPEN → @who], file:line, description, concrete fix suggestion]

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

### Standing items from prior review (PR reviews only)
Points raised earlier that are still unaddressed on the current head — confirmed, attributed, not re-discovered. [For each: who raised it + when, file:line, one-line status.] Omit if none.
```

End with a **recommendation**: what to fix first and why — leading with NEW findings and unmet acceptance criteria, and separating "worth a fresh round" from "these standing items still need the author's attention."

## Phase 6: Disposition & Posting (optional — public action, gated)

Only when the user wants to act on the review (fix things, or post a comment/review). Everything here is behind the **confirm-before-public-action** gate.

### Fix-forward split (team PRs)
On a team-member PR, don't default every finding to a comment — shipping an obviously-correct fix beats describing it and waiting a round-trip. Classify each finding:
- **Fix-forward** — one obviously-correct change (clear bug, missing error handling, dead code, typo). Implement it.
- **Comment-only** — tradeoffs, design questions, or any fix embedding an assumption you couldn't verify. When in doubt, comment.

**External-contributor PRs are always comment-only** — commenting teaches, and pushing to their branch takes over their work; offer mechanical fixes as GitHub ` ```suggestion ` blocks instead. Present the split for approval before implementing. For approved fix-forwards: one commit per concern (independently revertable), run the project's checks, **confirm before pushing**, and reference each commit in the review with a `git revert` escape-hatch.

### Draft the review
- **Main comment + inline comments** are complementary — don't repeat. The main comment carries themes and points that don't belong on a line; inline comments carry the actionable specifics (file:line, what to use instead).
- **Voice:** match the reviewer's established voice and the project's norms — concise, conversational, code-referencing, actionable, honest (credit good work too). No emoji, no "Great work" openers, no walls of headers/bullets. Include only points that actually came up.
- **Adversarial pass (mandatory, before showing the draft):** challenge every claim as if refuting it. *Verified or inferred?* — state inferences as such and turn unverifiable ones into questions. *Self-explanatory* to someone without the investigation context (plain cause-and-effect, not compressed jargon)? *No incident-time specifics* ("last night 02:08" → "a failed staging run"). *Does each comment earn its place?* — rare-path/non-blocking notes fold into the main comment or drop. *Already stated by the author?* — shrink to a one-line independent confirmation.

### Attach evidence
The Phase 3 artifacts are half the deliverable — a console table proves a finding to you, an image proves it to the author. Embed them: upload to GitHub, put the URLs in the body. See `references/posting.md`.

### Preview, then post
- **Preview in chat first — always.** Show the full body + every inline comment with its anchor, and iterate. Prior approval of an earlier draft does not carry to new content.
- **Stage as PENDING** (visible only to the user) so they can read it in the diff UI in context, then submit the verdict only once they have seen the exact text and named it.
- **Post through the API, never the GitHub web UI** — the UI's "Finish your review" panel silently overwrites an API-staged body and every image in it.
- The mechanics — payload shape, anchor rules, staging and iterating, dismissing your own stale blocker — are in **`references/posting.md`**. Read it before staging.

## Notes

- Each agent reads the actual code, not just the diff — this catches issues where changed code interacts with existing code
- Agents read CLAUDE.md and CONTRIBUTING.md to enforce project-specific rules, not just generic best practices
- **Convention discovery (Phase 1) is what makes "does this fit?" answerable** — without the shared-primitives inventory and the validation/type/naming conventions, agents fall back to generic best-practice and miss codebase-specific divergences
- **"Match the evidence to the claim" is the load-bearing rule.** The reuse and fit checks existed as agent instructions long before agents actually did them — they hand-waved ("no missed reuse" while an existing component sat unreused) until the shown grep was required. The same failure recurred one level up: an agent *quoted the exact line* that disabled a feature for users and filed it as a style nit, because nothing required it to state a behaviour claim in behaviour terms. Adding more lenses never fixes this; requiring the matching evidence does.
- **Duplication rules must point at pre-existing code, not just at the diff.** Every duplication check here once read "repeated across 2+ new files", which only fires when a single PR introduces both copies. The ordinary case is a PR adding the Nth copy of a shape that already exists N−1 times: the diff contains one instance and looks clean by construction. A related failure is scope-priming — an agent told "these three fields repeat at four sites" correctly proposed a three-field helper, while the actual duplicated unit was the entire response record, repeated across three tools and already drifted in field nullability, date format, and envelope placement.
- **The assumption a PR rests on is usually in someone else's source.** A review once turned on whether a handler factory ran per request or once per process — the difference between per-caller behaviour and a cross-request identity leak. A comment in the diff asserted the safe answer; two review bots passed the PR clean; no agent could check it, because the package wasn't in `node_modules`. Two `npm pack`s and a read of the dist settled it. Agents reason about the code in front of them and take library behaviour on trust, so this check has no natural owner but you — and it is exactly the class of assumption that makes a PR either fine or badly broken, with no middle.
- **Track B exists because Track A structurally cannot see removals.** Agents organized by code artifact (data, logic, components, tests) or code virtue (reuse, simplicity) all inspect the code that is *there*. "This used to happen and no longer does" is invisible to every one of them — it has no file to live in. That is why it needs its own agent and its own evidence type, not a checklist item inside an existing one.
- **Phase 0 (PR/issue context) is what makes a review of a PR-with-history worth reading** — without it the review re-litigates points the maintainer already resolved, misses acceptance criteria the diff silently fails, and can't tell a fresh find from a months-old standing blocker. The three ledgers (acceptance criteria / resolved / standing) turn a raw defect list into "here's what's actually new, here's what's still open, here's what you can ignore."
- **Runtime verification runs before synthesis on purpose.** Ranking findings before observing them produces confident, wrong severities — measurement routinely turns a "Major" into a nit, and the baseline A/B routinely surfaces something no agent proposed. A report written from code-reading alone is a list of hypotheses presented as findings.
- **3b's precondition rule comes from a near-miss.** A predicted focus regression measured identical on both builds — because the button being clicked wrote back the same value, so nothing re-rendered and the mechanism under test never ran. The probe was inert, the reading was clean, and the finding was real and nearly dropped. A confirmed defect announces itself; this failure mode is silent, which is why it needs a rule rather than attention.
- **Artifacts are the deliverable, not a by-product.** A number in a transcript is something the reader has to take on trust; an image is something they can check. That is why 3f's requirements are all-or-nothing — a capture that happened but explains nothing, or explains itself but was never linked, leaves the reader exactly where a bare assertion would have.
- **Don't build locally — the build you want is already deployed.** A production build is minutes of CPU for something CI runs on every push, and its output *is* the PR preview that Phase 3 drives, so running it yourself buys nothing the preview hasn't already given you. Getting CI green is the author's job, not the review's. Cheap checks are the opposite case: a type-check or a unit run is seconds, and running those **as evidence for a finding** — confirming a claimed breakage, mutation-testing a recommended test (3g) — is the point, not a detour. The rule is about cost and redundancy; read as "never execute anything" it produces reviews that recommend tests nobody has run.
- **Phases 0–5 take no public action.** Only Phase 6 does, and it never posts before the user has seen the exact text and named the verdict.
- Phases 3 and 6 are **project-agnostic**: they discover how to run, authenticate, seed, and post from the *project's own* `CLAUDE.md` / docs, so the skill stays portable across repos. If a project doesn't document these, ask rather than hardcoding.
