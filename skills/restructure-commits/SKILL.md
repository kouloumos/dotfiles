---
name: restructure-commits
description: Restructure a PR's messy commit history into clean logical commits. Analyzes the full diff, proposes groupings by concern, rebuilds commits from scratch while preserving authorship, and verifies zero code diff against the original.
argument-hint: <pr-number>
---

# Restructure Commits

Take a PR branch with messy/iterative commit history and rebuild it as clean, logical commits. PR number: `$ARGUMENTS`.

This is different from `/cleanup-history` (which folds existing fixup commits) — this skill **rebuilds the commit structure from scratch** based on logical groupings of the changed files.

## When to Use

- A PR has many small iteration commits that don't map to logical changes
- Commits overlap in scope (e.g., multiple commits touch the same files for the same feature)
- The branch has a mix of fixup commits, review feedback commits, and original work that doesn't cleanly autosquash
- You want atomic commits organized by concern, not by chronological development order

## Phase 1: Setup & Analysis

### Get PR info

```bash
gh pr view <PR#> --json number,title,headRefName,headRepositoryOwner,headRepository,baseRefName,state,maintainerCanModify,author
```

Extract the branch name, fork info, and original author.

### Switch to the PR branch

Check if you're already on the correct branch. If not, create a worktree from the PR branch. If the PR is from an external fork, fetch it first:

```bash
git fetch git@github.com:<headRepositoryOwner>/<repo>.git <headRefName>
my-toolkit worktree create <headRefName> --base FETCH_HEAD
```

After creating the worktree, `cd` into it so all subsequent operations happen there.

**Alternative:** If already on the correct branch in the current directory, stay there.

### Fetch latest base branch

```bash
git fetch upstream <base-branch>
```

### Analyze the branch

```bash
# Current commits
git log --oneline upstream/<base-branch>..HEAD

# Full diff stat — this is what the final result must reproduce exactly
git diff --stat upstream/<base-branch>..HEAD

# Per-file diff to understand what changed
git diff upstream/<base-branch>..HEAD

# Check for unrelated file changes (branch behind base)
git merge-base upstream/<base-branch> HEAD
```

### Identify the original author

```bash
git log --format='%an <%ae>' upstream/<base-branch>..HEAD | sort | uniq -c | sort -rn
```

The most frequent author is typically the contributor. If multiple authors contributed meaningfully, note this for Phase 4.

## Phase 2: Propose Commit Structure

### Analyze file groupings

Read the diffs and understand what each file change does. Group files by logical concern — not by which original commit introduced them.

Good grouping criteria:
- **Same feature/concern**: Files that implement a single logical change
- **Dependencies**: If file A imports something new from file B, they likely belong in the same commit or B's commit must come first
- **Tests with implementation**: Test files should be in the same commit as the code they test

### Check cross-dependencies between groups

For each proposed group, verify:
- Does any file in this group import from a file in a later group? If so, reorder.
- Can each commit build/compile on its own? The project must be valid after each commit.
- Are there circular dependencies between groups? If so, merge those groups.

### Present the plan

Show the user:

```
## Current History (<N> commits)
<list of all commits>

## Proposed Structure (<M> commits)

### Commit 1: <title>
Files: <list>
Why: <brief rationale>

### Commit 2: <title>
Files: <list>
Why: <brief rationale>
Depends on: Commit 1 (imports X from Y)

### Commit 3: <title>
Files: <list>
Why: <brief rationale>

## Files excluded (stale-base artifacts, if any)
<list, if any>
```

**Ask the user for explicit approval before proceeding.** They may want to adjust groupings, rename commits, or merge/split groups differently.

## Phase 3: Create Backup & Restructure

### Create backup branch

```bash
ORIGINAL_TIP=$(git rev-parse HEAD)
git branch backup/pr-<PR#>-pre-restructure "$ORIGINAL_TIP"
```

Inform the user that the backup branch was created. This makes the operation fully reversible and provides the reference point for verification.

### Reset onto current base

```bash
git reset --soft upstream/<base-branch>
git reset HEAD
```

This puts ALL branch changes as unstaged modifications on top of the current base. This simultaneously handles:
- Restructuring (we can re-commit in any order)
- Rebasing (we're now on top of the latest base)
- Phantom diff elimination (unrelated files match the base, so no diff)

### Check for stale-base artifacts

After the reset, `git status` may show files the PR never touched. This happens when the base branch moved forward after the contributor branched — the reset places the contributor's old tree on top of the new base, so any files added or changed on the base since then appear as modifications. Restore them and verify only the PR's actual files remain:

```bash
git checkout -- <file1> <file2> ...
git status --short
```

### Commit in logical groups

For each group in the approved plan, stage and commit:

```bash
git add <file1> <file2> ...
git commit -m "<commit message>"
```

Write clear commit messages following project conventions:
- Short subject line (50 chars max)
- Blank line
- Explanatory body describing what and why

### Verify nothing is left

After all commits:

```bash
git status --short
```

The only remaining items should be untracked files not part of the PR (e.g., `.scratch/`). If any tracked PR files remain unstaged, something was missed — investigate before proceeding.

## Phase 4: Preserve Authorship

The restructured commits will have the current user as both author and committer. Fix this so the original contributor remains the author:

```bash
AUTHOR="<contributor-name> <<contributor-email>>"
git rebase --onto upstream/<base-branch> upstream/<base-branch> HEAD \
  --exec "git commit --amend --no-edit --author=\"$AUTHOR\""
```

After this:
- **Author** = original contributor (who wrote the code)
- **Committer** = current user (who shaped the commits)

This is the correct Git convention. If the PR had multiple meaningful authors, discuss with the user how to attribute — options include using the primary contributor as author on all commits, or assigning authorship per-commit based on who wrote the bulk of that group's code.

### Update branch ref

If the rebase left you on a detached HEAD:

```bash
git branch -f <branch-name> HEAD
git checkout <branch-name>
```

## Phase 5: Verify

### Zero diff check

```bash
# Must be empty — identical source code
git diff backup/pr-<PR#>-pre-restructure HEAD -- src/

# Full diff — may show stale-base artifacts that were excluded, nothing else
git diff backup/pr-<PR#>-pre-restructure HEAD --stat
```

**If the src/ diff is NOT empty, STOP.** Something went wrong during restructuring. Show the diff to the user and investigate. Do NOT proceed to push.

### Show final history

```bash
git log --format='%h  Author: %an  %s' upstream/<base-branch>..HEAD
```

## Phase 6: Push

Force-push to the contributor's fork using an explicit lease to prevent overwriting any new work:

```bash
# Get the current remote SHA for the lease check
REMOTE_SHA=$(git ls-remote git@github.com:<fork-owner>/<fork-repo>.git <branch> | cut -f1)

git push --force-with-lease=<branch>:$REMOTE_SHA \
  git@github.com:<fork-owner>/<fork-repo>.git <branch>
```

Do NOT add the contributor's fork as a remote — push directly using the URL.

## Phase 7: Post PR Comment

Draft a comment explaining the restructuring and how to verify it.

### Template

```markdown
I force-pushed to restructure the branch from <N> commits into <M> clean logical commits:

1. `<commit-1-subject>`
2. `<commit-2-subject>`
3. `<commit-3-subject>`

The previous branch tip is preserved as `backup/pr-<PR#>-pre-restructure`. You can verify no code was lost:

```bash
git diff backup/pr-<PR#>-pre-restructure <branch-name> -- src/
# Expected: empty output (identical source code)
```
```

**Show the draft to the user for approval before posting.** Display the raw markdown so the user sees exactly what will be posted.

After approval:

```bash
gh pr comment <PR#> --body "<approved-comment>"
```

## Phase 8: Cleanup

- The local backup branch can be kept or deleted: `git branch -D backup/pr-<PR#>-pre-restructure`
- Inform the user the backup branch exists locally for reference
- If a worktree was created, remind the user it can be cleaned up after merge

## Notes

- **Always verify the diff is zero before pushing** — this is the critical safety check
- **Never push without user seeing the final plan and approving**
- **Never post PR comments without user approval**
- If the PR has only 1-2 clean commits already, this skill is overkill — suggest `/cleanup-history` instead
- If the branch just needs to be brought up to date, suggest `/rebase-pr` instead
- The `git reset --soft` approach handles both restructuring and rebasing in one operation — no separate rebase step needed
- Stale-base artifacts (files the PR never touched but show up as changed) are automatically eliminated since we reset onto the current base — just discard them before committing
