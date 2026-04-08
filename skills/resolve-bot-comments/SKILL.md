---
name: resolve-bot-comments
description: Review and resolve bot review comments on a PR. Critically evaluates suggestions from greptile-apps, cursor, and other bots.
argument-hint: <pr-number-or-url>
---

# Resolve Bot Comments Skill

You review bot-generated PR comments critically and resolve the valid ones. You don't blindly implement suggestions — you evaluate each one against the codebase context and only fix what makes sense.

## Supported Bots

- `greptile-apps[bot]` - Greptile code review bot
- `cursor[bot]` - Cursor AI review bot
- Any author containing `[bot]` in the name

## Phase 1: Setup & Branch Checkout

1. Parse the PR identifier from `$ARGUMENTS`. Extract the PR number (handle both raw numbers and full GitHub URLs).

2. Fetch PR metadata:
   ```bash
   gh pr view <number> --json title,body,headRefName,baseRefName,author,headRepositoryOwner,files,additions,deletions,url
   ```

3. **Switch to the PR branch.** Check if you're already on the correct branch:
   ```bash
   git branch --show-current
   ```

   If not on the PR branch, create a worktree from the PR branch. If the PR is from an external fork (headRepositoryOwner differs from the repo owner), fetch it first:
   ```bash
   git fetch git@github.com:<headRepositoryOwner>/<repo>.git <headRefName>
   my-toolkit worktree create <headRefName> --base FETCH_HEAD
   ```

   For branches on existing remotes:
   ```bash
   my-toolkit worktree create <headRefName> --base <headRefName>
   ```

   After creating the worktree, `cd` into the worktree directory so all subsequent reads, edits, and commits happen there.

   **Alternative:** If already on the correct branch in the current directory, stay there.

## Phase 2: Gather Bot Comments

1. Fetch all review comments (line-level comments on the diff):
   ```bash
   gh api repos/{owner}/{repo}/pulls/<number>/comments --paginate
   ```

2. Fetch general PR comments (conversation comments):
   ```bash
   gh api repos/{owner}/{repo}/issues/<number>/comments --paginate
   ```

3. Filter comments to only those from bots (authors containing `[bot]` in login or `type: "Bot"`).

4. **Skip already-resolved comments.** Use the GraphQL API to fetch review thread resolution status and cross-reference with bot comments:

   ```bash
   gh api graphql -f query='
     query($owner: String!, $repo: String!, $pr: Int!) {
       repository(owner: $owner, name: $repo) {
         pullRequest(number: $pr) {
           reviewThreads(first: 100) {
             nodes {
               id
               isResolved
               comments(first: 1) {
                 nodes { id databaseId }
               }
             }
           }
         }
       }
     }' -f owner='{owner}' -f repo='{repo}' -F pr=<number>
   ```

   Match each bot comment's `id` to the `databaseId` of the first comment in a review thread. If the thread's `isResolved` is `true`, the comment was explicitly resolved — exclude it from processing. Log how many were skipped so the user knows they were seen but not re-evaluated.

   **Important:** For unresolved bot comments, store the thread's GraphQL `id` (node ID, e.g. `PRT_kwDO...`) alongside the comment data. This thread node ID is needed in Phase 5 to programmatically resolve threads after posting replies.

5. Fetch the diff for reference:
   ```bash
   gh pr diff <number>
   ```

**If no unresolved bot comments exist:** Report this (including how many were skipped as already-resolved) and exit early.

## Phase 3: Critical Review

For each bot comment, evaluate it critically:

### Read Context First
- Read the file(s) mentioned in the comment
- Read surrounding code to understand the full context
- Check if the suggested change aligns with existing patterns in the codebase

### Classify Each Comment

Assign one of these verdicts:

| Verdict | Meaning |
|---------|---------|
| **VALID** | The comment identifies a real issue worth fixing |
| **INVALID** | The comment is wrong, misunderstands the code, or the suggestion would break things |
| **ALREADY_FIXED** | The issue was already addressed in a subsequent commit |
| **OUT_OF_SCOPE** | Valid observation but outside the scope of this PR |
| **NEEDS_DISCUSSION** | Subjective or architectural — requires human decision |

### Common Bot Mistakes to Watch For

- Suggesting changes that break existing functionality
- Misunderstanding intentional design decisions
- Flagging code that follows established project patterns
- False positives on security/performance (check if actually exploitable/impactful)
- Suggesting abstractions where simplicity is preferred
- Missing context from other files that explains the approach

### Prepare Reply for Each Comment

While classifying, draft a reply for each comment:

| Verdict | Reply Template |
|---------|----------------|
| **VALID** | Will be updated after fix is pushed — format: `Fixed in [force-push](<link>) — <brief explanation>` |
| **INVALID** | `False positive — <explanation of why the bot is wrong>` |
| **ALREADY_FIXED** | `Already addressed — <brief explanation of existing fix>` |
| **OUT_OF_SCOPE** | `Valid observation but outside the scope of this PR.` (optionally mention follow-up issue) |
| **NEEDS_DISCUSSION** | `This requires architectural decisions — <explanation of trade-offs>` |

Store each comment's `id`, `html_url`, and `threadNodeId` (from Phase 2) along with its verdict and draft reply for use in Phase 5.

## Phase 4: Implement & Commit Fixes

For each **VALID** comment:

1. Make the fix in the appropriate file
2. Verify the fix doesn't break anything (run relevant tests if available)
3. Keep track of what you changed and which commit the fix relates to

**Important constraints:**
- Don't over-engineer fixes — match the existing code style
- If a fix requires significant refactoring, mark as NEEDS_DISCUSSION instead
- If you're unsure about a fix, mark as NEEDS_DISCUSSION

### Commit Strategy: Fixup Commits

Fixes should be created as **fixup commits** that get squashed into the related original commit:

1. **Find the related commit** that introduced the code being fixed:
   ```bash
   git log --oneline -10 -- <file-path>
   ```

2. **Create a fixup commit** targeting that commit:
   ```bash
   git add <files>
   git commit --fixup=<original-commit-sha>
   ```

3. **After all fixes are committed**, squash them with autosquash rebase:
   ```bash
   # Count how many commits to include (original + fixups)
   GIT_SEQUENCE_EDITOR=true git rebase --autosquash HEAD~<N>
   ```

4. **Force push with lease** and capture the old/new remote tips:
   ```bash
   # Parse OLD_REMOTE_HEAD and NEW_REMOTE_HEAD from the push output.
   # git push --force-with-lease prints: "+ OLD_SHA...NEW_SHA branch -> branch (forced update)"
   # IMPORTANT: Do NOT use the pre-rebase local HEAD — fixup commits get squashed
   # away and won't exist on the remote, making comparison links broken.
   PUSH_OUTPUT=$(git push --force-with-lease 2>&1)
   OLD_SHORT=$(echo "$PUSH_OUTPUT" | grep -oP '^\+?\s*\K[0-9a-f]+(?=\.\.\.)' | head -1)
   NEW_SHORT=$(echo "$PUSH_OUTPUT" | grep -oP '\.\.\.(\K[0-9a-f]+)' | head -1)
   # IMPORTANT: Push output only shows abbreviated SHAs — resolve to full SHAs.
   # Both objects exist locally (old is in reflog, new is HEAD).
   OLD_REMOTE_HEAD=$(git rev-parse "$OLD_SHORT")
   NEW_REMOTE_HEAD=$(git rev-parse "$NEW_SHORT")
   ```

5. **Construct the force-push comparison link** for the PR comment:
   ```
   https://github.com/{upstream-owner}/{repo}/compare/{OLD_REMOTE_HEAD}..{NEW_REMOTE_HEAD}
   ```
   **CRITICAL:** The comparison link must use the **upstream repo** where the PR lives (from `gh pr view --json url`), NOT the fork that `git push` targets. Use `..` (two dots, direct diff), not `...` (three dots). The SHAs **must be full 40-character hashes** (abbreviated SHAs may not resolve on GitHub if the repo is large).

6. **Update VALID comment replies** with the fix information:
   - "Fixed in [force-push](<comparison-link>) — <brief explanation of what was changed>"

## Phase 5: Reply to Comments

After all fixes are pushed, prepare to reply to bot comments on GitHub.

### Prepare Summary Comment

If any VALID fixes were made, prepare a summary comment for the PR using numbered references to link to each addressed comment:

```markdown
I [force-pushed](<comparison-link>) to address bot review comment(s) ([1](<comment-1-url>), [2](<comment-2-url>)):

- <brief description of fix 1>
- <brief description of fix 2>
```

### Prepare Individual Replies

For each VALID comment, prepare a reply in this format:

```markdown
Fixed in [force-push](<comparison-link>) — <brief explanation of what was changed>
```

To post a reply to a review comment:
```bash
gh api repos/{owner}/{repo}/pulls/<pr-number>/comments/<comment-id>/replies \
  -f body="<reply-text>"
```

### Request User Approval

**IMPORTANT:** Before posting any replies, present them to the user for approval. Show the raw markdown in code blocks so the user sees exactly what will be posted:

````markdown
## Proposed GitHub Replies

### Summary Comment (on PR)
```
I [force-pushed](<comparison-link>) to address bot review comment(s) ([1](<comment-1-url>)):

- <brief description of fix 1>
```

### Individual Comment Replies

**Comment 1** (`<file>:<line>` — <verdict>)
> <original bot comment summary>

```
Fixed in [force-push](<comparison-link>) — <brief explanation>
```

---

Would you like me to post these replies? (You can also ask me to modify any of them first)
````

Only post replies after the user approves. If the user wants changes, update the replies and ask again.

### Post Replies (After Approval)

1. Post the summary comment to the PR (if there were VALID fixes):
   ```bash
   gh pr comment <number> --body "<summary-comment>"
   ```

2. Post individual replies to each bot comment:
   ```bash
   gh api repos/{owner}/{repo}/pulls/<pr-number>/comments/<comment-id>/replies \
     -f body="<reply-text>"
   ```

3. **Add thumbs-down reactions to INVALID comments.** Bots like Greptile learn from negative feedback. For every comment classified as **INVALID**, add a 👎 reaction:
   ```bash
   gh api repos/{owner}/{repo}/pulls/comments/<comment-id>/reactions \
     --method POST -f content="-1"
   ```
   Do this for all INVALID comments (including ALREADY_FIXED if the bot should have known better). Do NOT thumbs-down VALID, OUT_OF_SCOPE, or NEEDS_DISCUSSION comments.

4. **Resolve review threads for addressed comments.** After posting replies, programmatically resolve the review threads for comments classified as **VALID** or **ALREADY_FIXED** using the GraphQL `resolveReviewThread` mutation:
   ```bash
   gh api graphql -f query='
     mutation($threadId: ID!) {
       resolveReviewThread(input: { threadId: $threadId }) {
         thread { isResolved }
       }
     }' -f threadId="<thread-node-id>"
   ```
   Use the `threadNodeId` stored in Phase 2/3 for each comment. Only resolve threads where the issue has been definitively handled (VALID = fixed, ALREADY_FIXED = no action needed). Do NOT resolve OUT_OF_SCOPE, NEEDS_DISCUSSION, or INVALID threads — leave those for the PR author to review and resolve manually.

## Phase 6: Loop Check

After pushing fixes and posting replies, ask the user:

> "I've addressed X bot comments. Want me to wait for the bots to re-review and then process any new comments? (This may take a minute for bots to respond)"

If the user says yes:
1. Wait ~60 seconds for bots to re-analyze
2. Re-fetch bot comments (Phase 2)
3. Filter for NEW comments (not ones we already processed)
4. Repeat Phase 3-5 for new comments
5. Continue looping until no new VALID comments remain

## Phase 7: Generate Report

After all loops complete, produce a summary report:

```markdown
# Bot Comment Review Report

**PR:** #<number> - <title>
**Branch:** <headRefName>
**Total bot comments processed:** <count>

## Changes Made

- Force-pushed: [compare](<comparison-link>)
- Commits modified: <list of original commits that received fixups>

## Resolved (VALID)

### <file>:<line> — <bot-name>
> <original comment summary>

**Fix:** <description of what was changed>
**Reply posted:** Yes/No

---

## Skipped

### <file>:<line> — <bot-name> [INVALID]
> <original comment summary>

**Reason:** <why this was skipped>
**Reply posted:** Yes/No

---

## Needs Discussion

### <file>:<line> — <bot-name>
> <original comment summary>

**Question:** <what needs human input>
**Reply posted:** Yes/No

---

## Summary

- **X** issues fixed
- **Y** commits modified via fixup
- **Z** false positives identified
- **W** items need your review
- **N** loop iterations performed
- **M** replies posted to GitHub
```

Write the report to a file in the scratchpad directory and tell the user where to find it.

## Notes

- Always err on the side of caution — if unsure, classify as NEEDS_DISCUSSION
- If `my-toolkit worktree create` fails, fall back to `gh pr checkout <number>` or work in the current directory if already on the right branch
- Track which comments you've already processed (by comment ID) to avoid duplicates across loops
- Be especially skeptical of bot suggestions that would add complexity
- Trust explicit code comments that explain "why" something is done a certain way
- The `checkout_pr` shell function may be available as a fallback
- Never post replies without user approval
