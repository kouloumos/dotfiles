---
name: rebase-pr
description: Rebase a contributor's PR onto latest main. Fetches the PR, creates a backup branch on origin, sets up a worktree, analyzes divergence, rebases, and force-pushes back to the contributor's fork. Use when a PR needs to be brought up to date with main.
disable-model-invocation: true
allowed-tools: Bash, AskUserQuestion
argument-hint: <pr-number>
---

# Rebase PR

Rebase a contributor's pull request onto the latest main branch. PR number: `$ARGUMENTS`.

## Procedure

### 1. Get PR info

Fetch PR metadata:

```
gh pr view <PR#> --json number,title,headRefName,headRepositoryOwner,headRepository,baseRefName,state,maintainerCanModify,commits
```

Extract:
- **branch**: `headRefName`
- **fork owner**: `headRepositoryOwner.login`
- **fork repo**: `headRepository.name`
- **base branch**: `baseRefName`
- **state**: must be `OPEN`
- **maintainerCanModify**: must be `true`

### 2. Validate

- If the PR is not `OPEN`, **stop** and inform the user.
- If `maintainerCanModify` is `false`, **stop** and inform the user that maintainer push access is not enabled on this PR. They should ask the contributor to enable "Allow edits from maintainers".

### 3. Fetch PR and latest main

```
git fetch upstream pull/<PR#>/head
```

Record `FETCH_HEAD` as the PR tip SHA:
```
git rev-parse FETCH_HEAD
```

Also fetch the latest base branch:
```
git fetch upstream <base-branch>
```

### 4. Create backup branch

Before any mutation, create a backup branch from the original PR tip and push it to `origin` (personal fork) so the state is always recoverable and visible on GitHub:

```
git branch backup/pr-<PR#>-original <pr-tip-sha>
git push origin backup/pr-<PR#>-original
```

Inform the user that the backup branch was created and pushed to origin. This makes the operation fully reversible.

### 5. Create worktree

Create a detached worktree from the PR tip, then create a local branch:

```
git worktree add /tmp/rebase-pr-<PR#> --detach <pr-tip-sha>
```

Then inside the worktree:
```
cd /tmp/rebase-pr-<PR#>
git switch -C rebase/pr-<PR#>
```

**All subsequent git commands run inside this worktree directory.**

### 6. Analyze commits

From inside the worktree, analyze what needs rebasing:

- **Commits ahead**: `git log --oneline upstream/<base-branch>..HEAD | wc -l`
- **Commits behind**: `git log --oneline HEAD..upstream/<base-branch> | wc -l`
- **Unique commits** (not already in base via merges/cherry-picks): `git cherry -v upstream/<base-branch> HEAD`
  - Lines starting with `+` are truly unique to this branch
  - Lines starting with `-` are already in the base (merged via PRs, etc.)

### 7. Present the analysis

Show the user a clear summary:
- PR title and number
- How many commits ahead/behind
- How many are unique vs already-merged
- List the unique commits (the `+` lines from `git cherry`)

### 8. Choose strategy

Based on the analysis, recommend and explain one of these strategies:

**Strategy A - Simple rebase** (when all/most commits are unique):
```
git rebase upstream/<base-branch>
```

**Strategy B - Reset + cherry-pick** (when most commits are already in base and only a few are unique):
```
git reset --hard upstream/<base-branch>
git cherry-pick <commit1> <commit2> ...
```
This is cleaner when the branch has heavily diverged because rebase would replay already-merged commits, potentially causing spurious conflicts.

**Strategy C - Already up to date** (when 0 commits behind and no action needed):
Just inform the user and clean up the worktree.

### 9. Confirm before executing

Since both strategies involve potentially destructive operations:
- Show the exact commands that will be run
- Remind the user about the backup branch (`backup/pr-<PR#>-original` on origin)
- **Ask for explicit user confirmation before proceeding**

### 10. Execute

Run the chosen strategy inside the worktree. If cherry-picking multiple commits, apply them in chronological order (oldest first, as listed by `git cherry`).

If conflicts occur during rebase or cherry-pick:
- Stop and inform the user about the conflict
- Show the conflicting files
- Remind them the backup branch exists on origin and they can abort
- Provide the worktree path so they can resolve manually
- Do NOT attempt to auto-resolve conflicts

### 11. Verify

After successful execution:
- Run `git log --oneline -10` to show the resulting history
- Confirm the branch is now 0 commits behind the base
- Run `git diff upstream/<base-branch>...HEAD --stat` to show what the PR changes

### 12. Push

Force-push the rebased branch to the contributor's fork. Use `--force-with-lease` with the original SHA to ensure we don't overwrite any new commits the contributor may have pushed since we fetched:

```
git push git@github.com:<fork-owner>/<fork-repo>.git HEAD:<branch> --force-with-lease=<branch>:<original-pr-tip-sha>
```

Do NOT add the contributor's fork as a remote — push directly using the URL.

### 13. Post PR comment

Draft a comment explaining what happened and **show it to the user for approval before posting**. The comment should:
- State what was done (rebase or cherry-pick) and any notable changes (e.g. migration renames)
- Reference the backup branch on origin so the original state can be recovered (include a link to it)

**Tone depends on the contributor:**
- **Core contributors**: Direct and concise. No greeting, no explaining that main moved forward — they know the workflow. Just state what was done.
- **Non-core / new contributors**: Warm and friendly. Greet them ("Hey!"), explain context ("Main has moved forward and your branch was out of sync"), be welcoming.

Example for core contributor:
```
Rebased your commits on top of the current main and force-pushed the result.

The original branch state before the rebase is preserved at [`backup/pr-<PR#>-original`](https://github.com/<origin-owner>/<origin-repo>/tree/backup/pr-<PR#>-original), so nothing is lost.
```

Example for new contributor:
```
Hey! Main has moved forward and your branch was out of sync. I've rebased your commits on top of the current main and force-pushed the result to this PR branch.

The original branch state before the rebase is preserved at [`backup/pr-<PR#>-original`](https://github.com/<origin-owner>/<origin-repo>/tree/backup/pr-<PR#>-original) on our fork, so nothing is lost.

I'll continue reviewing shortly!
```

Post using:
```
gh pr comment <PR#> --body "<approved-comment>"
```

### 14. Clean up

- Remove the worktree: `git worktree remove /tmp/rebase-pr-<PR#>`
- Delete the local branch: `git branch -D rebase/pr-<PR#>`
- Delete the local backup branch: `git branch -D backup/pr-<PR#>-original`
- The backup branch remains on origin for reference
- Inform the user that they can delete the remote backup branch later with `git push origin --delete backup/pr-<PR#>-original`
