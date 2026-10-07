# The guided tour: the review as a walk through the real diff

Read this before Phase 5. It is the method for the review's main deliverable to the human reviewer: one page that walks the real diff in the order the change works, with the findings on their lines, the flow on the side, and real data where it explains something.

## Why this exists

The reviewer no longer reads every line; agents wrote most of them. The reviewer's job is to understand the change and decide. A list of findings does not give understanding: the reader must trust it or redo the work. The tour gives both: the change, in an order a human understands, with each finding at the point where the reader has just learned enough to judge it.

## What the first reviewer told us (keep this)

Three formats were tried on the first case (a two-repo pipeline change, ~100 hunks):

| Format | Verdict |
|---|---|
| A story page: chapters of prose, code excerpts, widgets | "A wall of text with not a lot of imagination." |
| A scroll story: prose on the left, a sticky stage with real data on the right | "Promising, but not there." Little actual code. |
| **A guided tour of the real diff** (this method) | **"I like this."** |

Feedback that shaped the tour, in their words where possible:
- "A guided tour of the actual diff … a balance of looking at code and having the overview, and the flow."
- A glossary and a reminder of the data-model entities involved. Call out words with two meanings ("label" meant three things).
- Real data first, walked step by step; a hypothetical "what if" only after the real case.
- "Go deeper" generated on demand: a prompt to post back to the session, not pre-built layers.
- The overview must show the big picture in 30 seconds.

## Scale: does this PR need a tour?

Decide in Phase 1, from the diff size and the kinds of change:
- **Full tour**: a change with a flow across components, a decision rule, a migration, or more than ~15 hunks of behaviour.
- **Short tour** (overview + 2–4 steps): a focused change in one place.
- **None**: a typo, a dependency bump, a two-line fix. The chat report is enough; say so.

## The pipeline

1. **Inventory (Phase 1).** `make_hunks.py --repo KEY=PATH:BASE:HEAD:OWNER/NAME … -o hunks.json`. Then one agent annotates every hunk (`inventory-prompt.md`): role, chapter, description, key hunks, focus ranges for large ones. Give the chapter map to the Phase 2 agents too; findings that name a chapter are easier to place.
2. **Author `tour.json` (Phase 5)**, after synthesis, when the findings are final. Contract: `tour/tour-schema.md`. The orchestrator writes it, not an agent: the tour needs one voice and the full picture.
3. **Build.** `build_tour.py --tour tour.json --hunks hunks.json -o index.html`. Exit 1 means a slice names an unknown hunk or a finding has no shown line: fix the tour, do not ignore it.
4. **Verify** (checklist below), then one **critique pass** by an agent, then fix what it finds.
5. **Publish** as a private Artifact (`Artifact` tool, icon `review`). Republish the same file path after changes, so the link stays. With media, publish the files alongside the page (see `tour-schema.md` § Media files). Never link it from the public review: it may hold production data.
6. **Collect feedback** (below). The tour improves only from what reviewers say about real ones.

Keep all working files in `~/review-<repo>-<pr>/` (tour.json, hunks.json, index.html, critique.md), not in the session scratchpad.

## Authoring the steps

Rules from the research on how reviewers read changes (Baum et al. 2017 on ordering change parts; Fregnan et al. 2022 on position and defect detection; Devin Review, CodeTour, Reviewable, PR Lens for the interface):

1. **Start with intent and an overview.** The overview step has no code: an `arch` block (the components, with the decisions linked), a before/after table on real records if you have them, the headline measurement, the asks (clickable), the legend.
2. **Definitions before use.** A "contract" step early: schema, types, wire formats.
3. **Important and risky parts early.** The decision rules, the migration, the security boundary. A defect in the last-read file was found with 64% lower odds.
4. **Group related hunks into one step, across files and repos, and show them together.** Grouping beats order. Then follow the runtime flow.
5. **Name every step and its place.** Title = what happens ("Wire out: the app builds the request"), section = where it sits in the story.
6. **Prose: 2–4 sentences** on what happens and why it matters. Never restate the code; captions say what the slice shows in the reader's terms.
7. **Code budget.** Show the key hunks open; collapse wiring, mirrors and tests. Cut large new files into slices at function boundaries (`r`). If a step shows more than ~250 open lines, split it or collapse more.
8. **Real records.** If the change processes data, follow 3–4 real records through the steps (`records` + per-record `panel` blocks): one normal case, one edge case, one that shows each finding. Precompute their data when building `tour.json`; the template does no domain logic.
9. **Findings on their lines**, as posted, plus a `forYou` line for this reader. Other reviewers' points appear dashed, as context. Body-level points with no line go in the step's `notes`.
10. **Callouts explain, findings judge.** 5–10 "how it works" callouts on the lines a reader would otherwise puzzle over, with the real record's numbers ("80 ≥ 0.6 × 85, so contested").
11. **2–4 "check here" questions per step**: what a reviewer should be able to answer before moving on.
12. **Glossary and entities.** Every term the change introduces, every word with two meanings, and the tables or types involved with one line each.
13. **Tests** in their own step, with a break-the-guard table if Phase 3 mutated anything: guard, test, caught or not.
14. **Last step: the drafts** as posted or staged (`drafts` block). When a capture makes a finding land faster for the author — a UI defect, an error page, an interaction — put it in the draft too, on its own line in GitHub's form (`tour-schema.md`, `drafts`). The tour shows it in place, so the reader approves the review with its pictures. Before staging, upload each file (`posting.md` § Embedding images and video) and swap the local path for the returned URL; rebuild so the last step shows what was posted.
15. **Pictures where the change is visible.** A step whose code changes what a user sees gets a screenshot of the result (`img`, or `ab` for desktop/phone or before/after), and a step that is a flow across pages gets a short recording (`video`). A finding that reproduced gets its capture in `media`, on its line. Capture with the same rules as SKILL.md 3f: highlight the element, put the state in a banner, hide dev overlays, and look at every image before it goes in. The reader should not need the preview to see what the step is about.

## Verify before publishing

- The build exits 0 (every slice resolves, every finding is placed).
- Serve it (`python3 -m http.server --bind 127.0.0.1`) and render **every step for every record** in the browser with a script; zero errors.
- Every `img` loads (`complete && naturalWidth > 0`) and every `video` reaches `readyState ≥ 2`, at both widths. After publishing, list the artifact's files (`Artifact` `list`, `scope: files`) and check each media path is there.
- Look once at desktop width (1440×900) and once at phone width (390×844): one-column layout, nothing cut, the top bar not eating the screen.
- Read the overview as a stranger: does it say what changed, how it works, what we found, in 30 seconds?
- Stop the server; reset the viewport.

## The critique pass

One agent, read-only, judges the built page as the reviewer who will use it. Give it: the page path, the reviewer's asks above, the authoring rules, and ask for (a) anything broken, (b) the 10–15 most valuable improvements, the top 5 marked "do now", each with what, why and how. Fix the broken items and the top 5; leave the rest in `critique.md`. The first critique found 7 broken things in a page that looked fine: no viewport tag, raw markdown tables, deep links, arrow keys stealing scroll, a coverage meter that over-counted, a dim diagram, a caption that overstated what was measured.

## Feedback loop

After the reviewer uses a tour, ask three questions and log the answers with the PR's shape (size, kinds of change, repos):
1. What did you use?
2. What did you skip?
3. Did you open the GitHub diff to understand something, and why?

Log them in the handoff file for this skill's iteration (see the session handoff). After 3–4 tours of different shapes, change the rules above from what the log says, not from taste.

## Known gaps (from the first critique)

- Values in the side panel are not linked to the code lines that produce them.
- ~~UI changes have no picture yet.~~ Added after the second tour (#810, 2026-10-07): `img`/`ab`/`video` blocks and finding `media`. The reviewer asked for it after using a tour without a single screenshot.
- Tests are a separate step; placing each next to the code it exercises may be better.
- "Go deeper" prompts are generic; per-step preset prompts may be more useful.
