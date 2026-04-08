---
name: cleanup-history
description: Analyze branch commits, identify fixup candidates, rebase with autosquash, and post a PR comment explaining the cleanup.
argument-hint: <optional: pr-number>
---

# Cleanup History

Clean up the commit history on the current branch before merging. Analyzes all commits since divergence from main, identifies which ones should be fixup commits folded into earlier commits, rebases with autosquash, force-pushes, and posts a PR comment documenting the cleanup.

## Git Workflow Context

This project uses a fork-based workflow. Contributors push to their fork (`origin`) and open PRs against the upstream repository (`upstream`). When running commands:
- **Base branch**: Use `upstream/main` if the `upstream` remote exists, otherwise `origin/main`
- **Push target**: Always push to `origin` (the contributor's fork)

## Phase 1: Setup & Context

### Determine base branch

```bash
git remote | grep -q upstream && BASE=upstream/main || BASE=origin/main
git fetch $(echo $BASE | cut -d/ -f1)
```

### Find the PR

If `$ARGUMENTS` contains a PR number, use that. Otherwise, detect from the current branch:

```bash
BRANCH=$(git branch --show-current)
gh pr list --head "$BRANCH" --json number,title,url --limit 1
```

If no PR is found, the skill can still clean up the history — just skip the PR comment step at the end.

### Check if branch needs rebasing

```bash
git log --oneline HEAD..$BASE | wc -l   # commits behind
```

**If the branch is behind the base (commits behind > 0), STOP.** Inform the user that the branch needs to be rebased onto the latest base first and instruct them to run `/rebase-pr` before re-running `/cleanup-history`. This keeps the rebase and the history cleanup as separate operations with distinct force-pushes and compare links.

### Gather commit data

```bash
# List all commits on the branch
git log --oneline $BASE..HEAD

# Show what each commit touches
git log --oneline --stat $BASE..HEAD

# Show full commit messages for context
git log --format="%H %s%n%n%b%n---" $BASE..HEAD
```

## Phase 2: Analyze & Classify Commits

For each commit on the branch, classify it as either a **standalone commit** or a **fixup candidate**.

### Identifying fixup candidates

A commit is a fixup candidate if it:

1. **Fixes, cleans up, or refines work from an earlier commit** — e.g., removing dead code, fixing imports, addressing review feedback, small corrections
2. **Touches the same files** as an earlier commit and the changes are incremental adjustments rather than new functionality
3. **Has a message that signals cleanup** — e.g., "fix:", "address review", "remove unused", "clean up", "simplify", "nit:"

### Matching fixups to targets

For each fixup candidate, determine which earlier commit it should fold into by:
- Analyzing which files it modifies and matching to the commit that introduced those changes
- Considering the commit message context
- If a fixup touches files from multiple earlier commits, assign it to the most relevant one (the one whose core changes it refines)

### What stays standalone

A commit stays standalone if it:
- Introduces genuinely new functionality or a distinct logical change
- Makes architectural changes that deserve their own commit message
- Cannot be cleanly attributed to a single earlier commit

## Phase 3: Present the Plan

Show the user a clear before/after view:

```
## Current History (oldest first)

1. abc1234 feat: add widget component
2. def5678 feat: redesign widget layout
3. ghi9012 fix: address review feedback
4. jkl3456 fix: remove dead imports

## Proposed Cleanup

Standalone commits (will remain):
  1. abc1234 feat: add widget component
  2. def5678 feat: redesign widget layout

Fixup targets:
  ghi9012 "fix: address review feedback" → fixup into abc1234 "feat: add widget component"
  jkl3456 "fix: remove dead imports" → fixup into abc1234 "feat: add widget component"

## Resulting History

1. abc1234 feat: add widget component     (absorbs ghi9012, jkl3456)
2. def5678 feat: redesign widget layout
```

**Ask the user for explicit approval before proceeding.** The user may want to adjust the plan — e.g., reassign a fixup to a different target, keep a commit standalone, or split things differently.

## Phase 4: Create Backup Branch

Before any mutation, create a backup branch from the current branch tip and push it to `origin` so the state is always recoverable:

```bash
BACKUP_BRANCH="backup/cleanup-$(git branch --show-current)-$(date +%Y%m%d-%H%M%S)"
ORIGINAL_TIP=$(git rev-parse HEAD)
git branch "$BACKUP_BRANCH" "$ORIGINAL_TIP"
git push origin "$BACKUP_BRANCH"
```

Inform the user that the backup was created and pushed. This makes the operation fully reversible — if anything goes wrong, the original history can be restored from the backup branch.

## Phase 5: Fold Fixup Commits

### Prepare the interactive rebase sequence

Build the rebase todo list by reordering commits so each fixup immediately follows its target, then marking fixup commits with `fixup`:

```bash
# Write the desired todo list to a script
# Use GIT_SEQUENCE_EDITOR to apply it non-interactively
GIT_SEQUENCE_EDITOR='bash /tmp/rebase-editor.sh' git rebase -i $BASE
```

**Implementation approach:**

1. Generate the desired todo list based on the approved plan
2. Write a shell script that overwrites the todo file with the desired sequence
3. Use `GIT_SEQUENCE_EDITOR='bash /path/to/script.sh'` to apply it non-interactively

The reordering must:
- Place each fixup commit immediately after its target
- Change `pick` to `fixup` for fixup commits
- Preserve the relative order of standalone commits

**If conflicts occur:**
- Stop and inform the user about the conflict
- Show the conflicting files and context
- Remind them the backup branch exists on origin and they can abort with `git rebase --abort`
- Do NOT attempt to auto-resolve conflicts

### Verify the result

After successful rebase:

```bash
# Show the new history
git log --oneline $BASE..HEAD

# Verify no code changes — diff the branch-modified files between old and new HEAD
git diff HEAD $ORIGINAL_TIP -- <list of files the branch modifies>
```

The diff of branch-modified files must be empty. If it differs, **stop and alert the user**.

## Phase 6: Push & Capture Compare Link

Force-push with lease and capture the before/after SHAs:

```bash
PUSH_OUTPUT=$(git push --force-with-lease 2>&1)
echo "$PUSH_OUTPUT"

# Parse old and new remote SHAs from push output
OLD_SHORT=$(echo "$PUSH_OUTPUT" | grep -oP '^\+?\s*\K[0-9a-f]+(?=\.\.\.)' | head -1)
NEW_SHORT=$(echo "$PUSH_OUTPUT" | grep -oP '\.\.\.(\K[0-9a-f]+)' | head -1)
CLEANUP_OLD_SHA=$(git rev-parse "$OLD_SHORT")
CLEANUP_NEW_SHA=$(git rev-parse "$NEW_SHORT")
```

Construct the comparison link:
```
https://github.com/{upstream-owner}/{repo}/compare/{CLEANUP_OLD_SHA}..{CLEANUP_NEW_SHA}
```

Use the **upstream repo** (where the PR lives) for the comparison URL, not the fork. SHAs **must be full 40-character hashes**.

Since the fixup folding only rewrites history without changing code, this compare link should show **no file changes** — confirming the cleanup was history-only.

## Phase 7: Post PR Comment

If a PR was identified in Phase 1, draft a comment explaining the cleanup.

### Draft the comment

The comment should:
- Explain that the commit history was cleaned up before merge
- Show the before and after commit structure — use bullet lists (not code fences) so GitHub auto-links commit SHAs
- Link to the compare so reviewers can verify no code changed
- Reference the backup branch (with a link) so the original state can be recovered
- Be clear and concise

Template:

```markdown
Cleaned up the commit history by [folding fixup commits](<cleanup-compare-link>) before merge (history-only, no code changes).

**Before** (<N> commits):
- <sha> <message>
- <sha> <message>
- ...

**After** (<M> commits):
- <sha> <message>
- <sha> <message>

<Brief explanation of what was folded into what>

Original branch state preserved at [`<backup-branch>`](<link-to-backup-branch-on-origin>) in case recovery is needed.
```

### Get approval and post

**Show the draft comment to the user for approval before posting.** Display the raw markdown in a code block so the user sees exactly what will be posted.

After approval:

```bash
gh pr comment <PR#> --body "<approved-comment>"
```

## Phase 8: Cleanup

After everything is confirmed working:
- Delete the local backup branch: `git branch -D "$BACKUP_BRANCH"`
- The backup branch remains on origin for reference
- Inform the user they can delete the remote backup later with `git push origin --delete "$BACKUP_BRANCH"`

## Notes

- Always verify the diff is identical before and after fixup folding — the cleanup must be history-only, no code changes
- If the branch has only 1 commit, there's nothing to clean up — inform the user and exit
- If no commits qualify as fixups, inform the user that the history already looks clean
- Never force-push without `--force-with-lease`
- Never post PR comments without user approval
- Never proceed with the rebase without creating the backup branch first
