---
name: merge-pr
description: Merge a pull request with a deliberately chosen merge method. Use when asked to merge a PR.
argument-hint: <pr-number-or-url>
disable-model-invocation: true
---

# Merge PR Skill

You merge PRs with a deliberately chosen merge method. The method is **never inferred** — not from the repo's history, not from repo settings, not from "what seems common". The user picks, every time.

## Phase 1: Preflight

1. Parse the PR identifier from the arguments (raw number or GitHub URL).
2. Discover the repo: `gh repo view --json nameWithOwner`. Use this slug for all `gh api` calls.
3. Gather merge readiness in one pass:
   - `gh pr view <N> --json state,mergeable,mergeStateStatus,reviewDecision,baseRefName,headRefName,title`
   - `gh pr checks <N>` — CI status
   - `gh api repos/<owner>/<repo> --jq '{allow_squash_merge, allow_merge_commit, allow_rebase_merge, delete_branch_on_merge}'` — which methods the repo permits
4. If the PR is not open, not mergeable, CI is failing, or review is not approved: report exactly what's blocking and stop. The user decides whether to override (e.g. merge with a pending optional check).

## Phase 2: Analyze commit structure

The merge method should follow from what the branch's commits are worth preserving. Look at them:

```
gh pr view <N> --json commits --jq '.commits[] | .messageHeadline'
```

Classify the branch:

- **Structured multi-commit**: several commits, each a distinct logical change with meaningful messages (e.g. conventional-commit style, deliberate feature/refactor split). These commits carry information a squash would destroy.
- **Single commit**: nothing to preserve or collapse; methods differ only cosmetically.
- **Messy**: WIP commits, `fixup!`s, "address review comments", checkpoint noise. The individual commits carry no information worth keeping.

## Phase 3: Present options

Present the allowed methods with what each one does **to this specific PR's history**, and a recommendation tied to the classification — but let the user choose. Never pre-select based on the base branch's existing history: repos often mix styles, so past merges are not evidence of a convention.

Typical mapping (adapt the wording to the actual commits):

| Branch shape | Recommendation | Why |
|---|---|---|
| Structured multi-commit | Merge commit | Preserves the commit structure on the base branch |
| Single commit | Squash (or rebase) | Equivalent outcomes; squash adds the `(#N)` back-reference |
| Messy | Squash — or clean up first | Collapsing noise is the point; alternatively run /cleanup-history or /restructure-commits, then merge-commit |

Show the actual commit list alongside the options so the user sees what would be preserved or collapsed.

## Phase 4: Final confirmation — always

Even after the user picks a method, confirm once more before executing, restating the full action in one line:

> Merging PR #553 ("<title>") into `<base>` with a **merge commit** — the branch's 3 commits land on `<base>` under a merge commit. Go?

This is mandatory. A merge is irreversible in practice (rewriting a shared base branch to undo one is disruptive), so no merge happens on an earlier "yes" carried forward — the confirmation must be for this exact method and PR.

## Phase 5: Execute and verify

1. `gh pr merge <N> --merge|--squash|--rebase` per the choice.
2. Verify: `gh pr view <N> --json state,mergedAt,mergeCommit` — report the resulting SHA on the base branch.
3. Post-merge follow-ups — offer, don't assume:
   - Delete the remote branch (only if `delete_branch_on_merge` is false; note that deleting is skippable if the branch history is worth keeping after a squash).
   - Clean up local state: worktree removal, local branch deletion, fetching the updated base.
