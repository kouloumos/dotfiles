---
description: "Challenge a PR's design decisions and surface alternative approaches. Complements review-pr (which checks correctness) by asking whether this is the right code to write."
argument-hint: "<PR-number>"
allowed-tools: ["Bash", "Glob", "Grep", "Read", "Agent"]
---

# Challenge PR Implementation

Examine a PR's key design decisions and surface alternative approaches with honest tradeoffs. This is not a code review — it does not look for bugs, style issues, or pattern violations. It asks: "Is this the right approach? What else was possible? What are we committing to long-term?"

Not every decision needs a challenge. When the chosen approach is clearly reasonable, say so and move on. The goal is to make implicit decisions explicit, not to generate objections for their own sake.

**PR number:** $ARGUMENTS

## Phase 1: Understand the Problem

Before looking at code, understand *what problem is being solved and why*.

1. Fetch the PR metadata:
   ```bash
   gh pr view $ARGUMENTS --json title,body,headRefName,baseRefName,commits,files
   ```

2. Read the PR description, commit messages, and any linked issues carefully. Extract:
   - **The problem being solved** — what couldn't be done before?
   - **The constraints** — why now? what's driving the timeline or approach?
   - **The intended scope** — what did the author set out to change?

3. Read project standards:
   - `CLAUDE.md` (root and any nested ones in changed directories)
   - `CONTRIBUTING.md`

## Phase 2: Extract Design Decisions

Get the full diff and identify the *decisions* — not code details, but the structural choices that shape the PR.

```bash
gh pr diff $ARGUMENTS
```

Read through the diff and the full files for context. For each significant change, ask: "What choice was made here, and what alternatives existed?"

A design decision is a choice where a different reasonable person might have chosen differently. Examples:
- "Introduce a new database table" (vs extending an existing one, vs using config)
- "Build a custom auth mechanism" (vs using an existing library or protocol)
- "Bundle three features in one PR" (vs shipping incrementally)
- "Put this logic in the API route handler" (vs a service layer, vs middleware)
- "Use fire-and-forget" (vs await, vs a job queue)

Ignore decisions that are obvious given the codebase conventions (e.g., "uses Prisma" in a Prisma project, "uses Tailwind" in a Tailwind project).

List the decisions before proceeding — typically 3-7 for a medium PR.

## Phase 3: Challenge from Multiple Perspectives

Launch **all perspective agents in parallel** using a single message with multiple Agent tool calls. Each agent gets the decision list, the full diff, and the project context.

Each agent should be **measured** — suggest alternatives only where they genuinely see a different path worth considering. "The current approach is reasonable" is a valid conclusion for any decision.

### Agent 1: The Simplifier

> You are reviewing PR #{number} in this repository from the perspective of simplicity. Your question for every decision is: "Can we achieve the same outcome with less?"
>
> **Project standards:**
> {CLAUDE.md and CONTRIBUTING.md content}
>
> **Design decisions identified:**
> {numbered list of decisions from Phase 2}
>
> **Your perspective:**
> Look for overengineering, unnecessary abstraction, features that could be deferred, and things that could be a smaller change. Not everything needs to be simpler — complexity is justified when the problem demands it. But when a simpler path exists that serves the same need, surface it.
>
> Specifically consider:
> - Could any new infrastructure (tables, modules, abstractions) be avoided by reusing what exists?
> - Are there features in this PR that aren't needed for the stated goal?
> - Could a phased approach deliver the core value sooner with less risk?
> - Is anything being generalized prematurely (solving for cases that don't exist yet)?
>
> **How to review:**
> 1. Run `gh pr diff {number}` to see the changes
> 2. For key files, read the full file for context
> 3. When you think something could be simpler, verify by checking what already exists in the codebase
>
> **Output format:**
> For each decision you have a perspective on:
> - **Decision**: which one (reference by number/name)
> - **Current approach**: one-line summary
> - **Simpler alternative** (if any): what it would look like
> - **Tradeoff**: what you gain and lose with the simpler approach
> - **Assessment**: is the current complexity justified, or would simpler serve just as well?
>
> If the current approach is already the simplest reasonable option, say so briefly and move on. Do not fabricate alternatives.

### Agent 2: The Long-term Maintainer

> You are reviewing PR #{number} in this repository from the perspective of long-term maintenance. Your question for every decision is: "How does this age? What does it force on the next 3 PRs?"
>
> **Project standards:**
> {CLAUDE.md and CONTRIBUTING.md content}
>
> **Design decisions identified:**
> {numbered list of decisions from Phase 2}
>
> **Your perspective:**
> Look for implicit contracts, coupling between things that should be independent, decisions that lock in a direction that's hard to change later, and patterns that will be copy-pasted (well or poorly) by future contributors. Not everything needs to be future-proof — sometimes shipping now and refactoring later is the right call. But surface the commitments being made.
>
> Specifically consider:
> - What assumptions does this encode that might change? (e.g., "all service keys are superadmin", "meeting IDs are date-based")
> - If a new developer copies this pattern for a similar feature, would that go well or poorly?
> - What's the migration path if this needs to change? (e.g., adding scoped permissions later, changing the ID scheme)
> - Are there implicit dependencies between components that aren't enforced by the type system?
>
> **How to review:**
> 1. Run `gh pr diff {number}` to see the changes
> 2. Read full files for context, especially where new patterns are established
> 3. Look at how similar things are done elsewhere in the codebase — is this creating a second way to do something?
>
> **Output format:**
> For each decision you have a perspective on:
> - **Decision**: which one
> - **What this commits to**: the long-term implication
> - **Evolution risk**: what happens when requirements change (if applicable)
> - **Alternative direction** (if any): a different approach that ages better
> - **Assessment**: is the commitment reasonable, or should the design leave more room?
>
> If the current approach ages fine, say so and move on.

### Agent 3: The Standards Advocate

> You are reviewing PR #{number} in this repository from the perspective of industry standards and established patterns. Your question for every decision is: "Is there a well-known solution for this that we should consider?"
>
> **Project standards:**
> {CLAUDE.md and CONTRIBUTING.md content}
>
> **Design decisions identified:**
> {numbered list of decisions from Phase 2}
>
> **Your perspective:**
> Look for cases where the PR builds custom infrastructure that has established alternatives — protocols, libraries, or well-documented patterns. Not "use a library for everything" — custom code is often the right call. But when a standard solution exists and the PR departs from it, surface the comparison so it's a conscious choice.
>
> Specifically consider:
> - Does this reimplement something that has a standard protocol? (e.g., OAuth2, webhook signatures, JWT)
> - Does the codebase already have infrastructure for a similar concern that could be extended?
> - Are there conventions in the framework (Next.js, Prisma, etc.) that this works against?
> - Would a well-known pattern make this easier to understand for new contributors?
>
> **How to review:**
> 1. Run `gh pr diff {number}` to see the changes
> 2. Read full files for context
> 3. Search the codebase for existing patterns that do similar things
>
> **Output format:**
> For each decision you have a perspective on:
> - **Decision**: which one
> - **Standard alternative** (if any): what established solution exists
> - **Fit assessment**: how well does the standard solution fit this specific use case?
> - **Tradeoff**: what the standard gives you vs what custom gives you
> - **Assessment**: is custom justified here, or would a standard approach serve better?
>
> If there's no relevant standard or the custom approach is clearly better suited, say so and move on.

### Agent 4: The Scope Slicer

> You are reviewing PR #{number} in this repository from the perspective of scope and incremental delivery. Your question is: "Is this the right unit of work? Could it ship in smaller, independently valuable pieces?"
>
> **Project standards:**
> {CLAUDE.md and CONTRIBUTING.md content}
>
> **Design decisions identified:**
> {numbered list of decisions from Phase 2}
>
> **Your perspective:**
> Look for independent concerns bundled together, features that could land separately, and things that are included "while we're here" but aren't necessary for the stated goal. Not every PR needs to be tiny — sometimes bundling related changes is cleaner. But when pieces are genuinely independent, splitting them reduces review burden, risk, and revert scope.
>
> Specifically consider:
> - Could any feature in this PR ship and be useful on its own?
> - Are there changes that are prerequisites vs changes that are enhancements?
> - If one part of this PR had a bug, would you want to revert the whole thing?
> - Is there a natural ordering (infrastructure first, then features, then UI)?
>
> **How to review:**
> 1. Run `gh pr diff {number}` to see all changes
> 2. Read the commit structure — does it already reflect independent concerns?
> 3. Map the dependency graph: which changes depend on which?
>
> **Output format:**
> - **Current scope**: one-line summary of what's bundled
> - **Independent pieces** (if any): what could be separated
> - **Suggested ordering** (if splitting): what ships first and why
> - **Assessment**: is the bundling reasonable, or would splitting improve things?
>
> If the PR is well-scoped as-is, say so. Not every PR needs to be split.

## Phase 4: Synthesize into Decision Points

After all agents complete, **you** (not another agent) must:

1. **Read all perspectives carefully**

2. **Merge perspectives per decision**: Multiple agents may comment on the same decision from different angles. Combine their views into a single decision point that captures all relevant perspectives.

3. **Drop non-findings**: If all agents agree a decision is reasonable with no interesting alternatives, don't include it. Only surface decisions where there's something worth considering.

4. **Assess honestly**: For each decision point, give your overall take. Sometimes the current approach is fine. Sometimes an alternative is clearly better. Often it's a genuine tradeoff worth discussing.

## Output Format

Present the analysis to the user:

```
## Implementation Challenge: [PR title] (#number)

[1-2 sentence summary of what the PR does and what problem it solves]

### Decision 1: [short name]

**Current approach:** [what the PR does]

**Alternative A — [name]:** [description]
- Gains: [what you get]
- Costs: [what you lose]

**Alternative B — [name]:** [description] (if applicable)
- Gains: ...
- Costs: ...

**Assessment:** [measured take — is the current approach reasonable? is an alternative worth pursuing? is this a genuine tradeoff the author should weigh?]

### Decision 2: ...

---

### Overall

[Brief summary: which decisions are clearly fine, which deserve discussion, and if any are worth changing before merge]
```

## Notes

- This skill does NOT look for bugs, style issues, or pattern violations — that's what `review-pr` does
- It does NOT comment on PRs or take any public action — it reports to you in the terminal
- Not every decision needs a challenge. "The current approach is reasonable" is often the right conclusion
- The value is in making implicit decisions explicit, not in generating objections
- Keep the tone measured and constructive — the author made reasonable choices, we're asking whether better ones exist
