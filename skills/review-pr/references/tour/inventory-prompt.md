# Hunk inventory: agent prompt

Run `make_hunks.py` first (it writes every hunk with exact text and ranges). Then give one agent this prompt, filled in. The inventory is what makes the tour complete by construction, so the agent must account for every hunk.

---

Read-only on the repos. Do not commit, push, or post.

Annotate the hunk inventory at `{HUNKS_JSON}` (written by `make_hunks.py`; do not change `id`, `text` or the ranges). It covers {PR_LIST}. The checkouts are at {CHECKOUTS}.

The change, in two sentences: {INTENT}.

Proposed chapters (the runtime path the tour will follow; add one if a hunk fits none, e.g. "contract: schema and types", "i18n", "docs/config"):
{CHAPTER_LIST}

For every hunk, fill in:
- `description`: one sentence on what the hunk does. Read the surrounding code to write it; never restate the code.
- `role`: one of `core` (carries behaviour), `wiring` (plumbing, types, imports passing data through), `guard` (auth, protection, validation), `test`, `ui-copy` (strings), `docs`, `config/noise` (lockfiles, generated, unrelated blocks).
- `chapter`: exactly one chapter id.
- `key`: true for the 1–3 hunks per chapter a reviewer must read; the rest are skimmable.
- `focus`: for hunks over 60 lines (usually new files), the new-line ranges that matter, as `[[start, end], …]`. Cut at function boundaries.

Then add to the top level:
- `chapters`: `[{id, title, summary (2 sentences), hunkIds (in reading order: entry point first, then callees), keyHunkIds}]`.
- `bodyPoints` (optional): for each review finding given to you as `{path, line, text}`, the hunk it sits in.
- `stats`: hunks and changed lines per repo, per chapter, per role.

Validate before you finish: every hunk appears in exactly one chapter's `hunkIds`; the JSON parses. Report (under 400 words): the stats, the chapter list with hunk counts, the 5 largest hunks, and every classification you were unsure about.
