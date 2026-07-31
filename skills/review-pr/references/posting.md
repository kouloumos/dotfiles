# Posting a review through the API

Read this when you are about to stage or submit a review. The mechanics are fiddly and the failure modes are silent.

## Why the API and not the UI

**Post via the API, never the GitHub web UI.** The UI's "Finish your review" panel overwrites an API-staged body with whatever is in its textarea — which is empty — so submitting from the UI silently destroys the review body and every embedded image.

## Staging a pending review

A **PENDING** review is visible only to its author. That makes it the right preview mechanism: the user reads it in the diff UI, in context, before anyone else sees it.

Build the payload as JSON and pass it with `--input`. Multi-paragraph bodies with backticks do not survive shell quoting; build the file with `python3` if `jq` is absent.

```
POST /repos/{owner}/{repo}/pulls/{n}/reviews
{ "commit_id": "<head sha>", "body": "...", "comments": [ {path, line, body}, ... ] }
```

**Omitting `event` is what makes it PENDING.** Include `event` only when submitting directly.

Guard against the two silent failures:

- An empty or malformed `--input` file creates an empty PENDING review. Assert the payload before POSTing — that `event` is absent, that the body is non-empty, that the comment count is what you expect.
- Anchors must land inside a diff hunk **including its context lines**. Check with the default-context diff, not `-U0`; a line that only appears in `-U0` output will be accepted but a line outside the hunk entirely will be rejected or silently degraded to a file-level comment. Verify after staging: each comment should report `subject_type: "line"` and a non-null `position`.

## Submitting a verdict

```
POST /repos/{owner}/{repo}/pulls/{n}/reviews/{review_id}/events
{ "event": "APPROVE" | "COMMENT" | "REQUEST_CHANGES" }
```

The staged body and comments are preserved. Never submit before the user has seen the exact text and named the verdict.

## Iterating on a staged review

There is no API to restructure a pending review's inline comments. To revise, **delete and recreate**:

```
DELETE /repos/{owner}/{repo}/pulls/{n}/reviews/{review_id}
```

This mints a **new review id**, so tell the user the new id and that their open tab needs a refresh — otherwise they will be reading the deleted one and reporting that nothing changed.

Before restaging, sweep the payload for statements that were true in an earlier draft and no longer are ("the one regression I found", "Approved", "I did not test X"). Findings that arrive late invalidate framing written earlier.

## Review state, and clearing your own blocker

`reviewDecision` reflects the latest review **per user**. A `COMMENT` review does not clear your own earlier `CHANGES_REQUESTED`; only an approval or a dismissal does.

**You can dismiss your own review through the API even though the web UI hides the option:**

```
PUT /repos/{owner}/{repo}/pulls/{n}/reviews/{review_id}/dismissals
{ "message": "why" }
```

The review body stays visible and readable, marked dismissed, with the message attached. Dismissing removes the block — so confirm that's intended when real issues are still open, since it removes the only mechanical guardrail.

## Embedding images and video

GitHub's user-attachments CDN has no API. Use the scrape-then-`gh api` flow in `browser-scripting`'s `references/github-image-upload.md`: a logged-in Playwright session uploads the file and yields a URL, then the URL goes in the body posted through the API.

Keep the session file outside the repo (a scratchpad, not `.scratch/`) unless that directory is gitignored — it holds a live GitHub session. Delete it when done.

Sizing: `<img width="900" src="...">` for a wide A/B composite, `<img width="380">` for a tight annotated crop, a **bare URL on its own line** for video.
