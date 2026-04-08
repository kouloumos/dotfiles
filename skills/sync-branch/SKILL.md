---
name: sync-branch
description: Sync a feature branch with the target branch (main by default). Analyzes divergence, identifies truly unique commits vs already-merged ones, and executes the cleanest rebase strategy. Use when a branch has fallen behind or diverged from main.
disable-model-invocation: true
allowed-tools: Bash
argument-hint: [target-branch]
---

# Sync Branch

Sync the current feature branch onto the latest target branch. The target branch defaults to `main` if not specified: `$ARGUMENTS`.

## Procedure

### 1. Pre-flight checks

- Verify the working tree is clean (`git status`). If there are uncommitted changes, **stop and tell the user** to commit or stash first. Do NOT stash on their behalf.
- Confirm we are NOT on the target branch itself. Refuse to proceed if so.

### 2. Fetch and analyze

Run these commands to understand the branch state:

```
git fetch origin <target-branch>
```

Then gather:
- **Commits ahead**: `git log --oneline origin/<target-branch>..HEAD | wc -l`
- **Commits behind**: `git log --oneline HEAD..origin/<target-branch> | wc -l`
- **Unique commits** (not already in target via merges/cherry-picks): `git cherry -v origin/<target-branch> HEAD`
  - Lines starting with `+` are truly unique to this branch
  - Lines starting with `-` are already in the target (merged via PRs, etc.)

### 3. Present the analysis

Show the user a clear summary:
- How many commits ahead/behind
- How many are unique vs already-merged
- List the unique commits (the `+` lines from `git cherry`)

### 4. Choose strategy

Based on the analysis, recommend and explain one of these strategies:

**Strategy A — Simple rebase** (when all commits on the branch are unique):
```
git rebase origin/<target-branch>
```

**Strategy B — Reset + cherry-pick** (when most commits are already in target and only a few are unique):
```
git reset --hard origin/<target-branch>
git cherry-pick <commit1> <commit2> ...
```
This is cleaner than rebase when the branch has heavily diverged because rebase would try to replay dozens of already-merged commits, potentially causing spurious conflicts.

**Strategy C — Already up to date** (when 0 commits behind and no action needed):
Just inform the user.

### 5. Create backup branch

Before any destructive operation, create a backup of the current branch state:

```
git branch <branch-name>-backup-sync
```

Also push the backup to origin so it can be referenced in PR comments:

```
git push origin <branch-name>-backup-sync
```

Inform the user that the backup was created locally and on origin. This makes the operation fully reversible.

### 6. Confirm before executing

Since both strategies involve potentially destructive operations (`rebase` can cause conflicts, `reset --hard` discards the current branch position):
- Show the exact commands that will be run
- Remind the user about the backup branch
- **Ask for explicit user confirmation before proceeding**

### 7. Execute

Run the chosen strategy. If cherry-picking multiple commits, apply them in chronological order (oldest first, as listed by `git cherry`).

If conflicts occur during rebase or cherry-pick:
- Stop and inform the user about the conflict
- Remind them the backup branch exists if they want to abort
- Do NOT attempt to auto-resolve conflicts
- Provide guidance on how to resolve and continue

### 8. Verify

After successful execution:
- Run `git log --oneline -10` to show the resulting history
- Confirm the branch is now 0 commits behind the target

### 9. Push to the PR branch

If the branch is associated with a PR from a contributor's fork:
1. Use `gh pr view <PR#> --json headRefName,headRepositoryOwner,headRepository,maintainerCanModify` to get the fork URL and branch name
2. Verify `maintainerCanModify` is true
3. Force-push directly to the contributor's fork using a URL (do NOT add their fork as a remote):
   ```
   git push git@github.com:<owner>/<repo>.git HEAD:<branch-name> --force
   ```

If the branch is on origin, force-push normally:
```
git push origin <branch-name> --force
```

### 10. Post PR comment

If there is an associated PR, post a comment explaining what happened. The comment should:
- Explain that main has moved forward and the branch was out of sync
- Mention that commits were cherry-picked on top of current main and force-pushed
- Link to the backup branch on origin: `[<branch-name>-backup-sync](https://github.com/<origin-owner>/<repo>/tree/<branch-name>-backup-sync)`
- Mention that review will be completed soon

Example:
```
Hey! Main has moved forward quite a bit and your branch was no longer in sync. To get things back into a clean and reviewable state, I cherry-picked your commits on top of the current main and force-pushed the result to this PR branch.

To be safe, I've also kept a backup of your original branch (before the cherry-pick) here: [`<backup-branch>`](https://github.com/<owner>/<repo>/tree/<backup-branch>)

I'll finish reviewing this shortly!
```

### 11. Clean up

- Delete the local backup branch: `git branch -D <branch-name>-backup-sync`
- The remote backup branch is kept for reference
