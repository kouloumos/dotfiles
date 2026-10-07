# tour.json: the contract

`build_tour.py --tour tour.json --hunks hunks.json -o index.html` turns this file plus the annotated hunk inventory into one self-contained page (`template.html`). Everything below is data; the template has no PR-specific code.

## Top level

| Field | What it holds |
|---|---|
| `id` | Stable id; the page keys its local "seen" state on it. Use `<repo>-<pr>`. |
| `title`, `intent` | Name in the top bar (2–4 words), and one line on what the change does. |
| `repos` | `{key: {label, tone, github}}`. `key` matches the hunk inventory. `tone`: `primary`, `secondary`, `external`, `neutral`. |
| `lanes`, `messages` | The sequence diagram. Lanes: `[{id, label, tone}]`, left to right. Messages: `[{from, to, label, steps: [stepId, …]}]`, top to bottom; the first step id is where a click jumps. Omit both when the change has no flow across components. |
| `glossary` | `[[term, definition]]`. The change's own terms, and any word with two meanings. Terms are auto-underlined in prose and open the drawer. |
| `entities`, `entityPath` | The data model the change touches: `[[name, one line]]`, and a one-line path such as `A → B → C`. |
| `records`, `recordPrompt` | Optional. Real records the reader can follow through the steps: `[{key, title, why}]`. Each step's `panel` can then hold blocks per record key. |
| `steps` | The tour. See below. |
| `findings` | Review findings anchored to a line (see below). |
| `callouts` | "How it works" notes on lines: `[[repo, path, line, text]]`. Explanation, not judgement. |
| `tailSteps` | Optional prose for the two generated closing steps: `{restNew, rest, section}` (`section` defaults to "The rest"). |
| `drafts` | `{label: markdown}`: the review drafts, shown by a `drafts` block. A draft can carry media in the form GitHub takes: a line with only `<img width="900" alt="…" src="…">` or `![alt](src)`, or a bare video path or URL on its own line. Local paths go through the same media check and copy; `https:` URLs (an uploaded GitHub attachment) are left as they are. |

## A step

```json
{
  "id": "wire-out", "section": "The flow", "title": "Wire out: the app builds the request",
  "where": ["app"],
  "prose": ["2–4 sentences: what happens here and why it matters. `code` and **bold** work."],
  "blocks": [ {"type": "h", "text": "…"}, {"type": "table", "head": ["…"], "rows": [["…"]]} ],
  "slices": [
    {"h": "app-db-utils-4", "cap": "what this slice shows, in reader terms"},
    {"h": "app-lib-thing-1", "r": [40, 80], "cap": "a range of a large new file"},
    {"h": "app-db-utils-1", "collapsed": true}
  ],
  "checks": ["A question the reader should answer before moving on."],
  "notes": [ {"who": "ours", "sev": "minor", "title": "A finding with no line in the diff", "text": "…"} ],
  "panel": { "_": [blocks for everyone], "<recordKey>": [blocks for that record] }
}
```

- `slices`: `h` is a hunk id; `r` is a new-line range inside it (omit for the whole hunk). `collapsed: true` for wiring, mirrors and tests. A slice that carries a finding opens anyway.
- The build appends two steps before a step with id `verdicts` (or at the end): "The unfocused parts of new files" (leftover lines of `core`, `test` and `guard` hunks) and "Everything else: safe to skip". So the tour shows every changed line.
- Section names group steps in the rail. Suggested order: Start → Definitions → the decisions or core logic → The flow → People/UI → Evidence → Decide.

## A finding

```json
{"repo": "tasks", "path": "src/lib/x.ts", "line": 136, "who": "ours", "pr": "#101", "sev": "minor",
 "title": "The posted first sentence", "text": "The full posted comment (markdown, tables work)",
 "forYou": "One line, written for the reader of this page, not the PR author."}
```

- `who`: `ours`, `explain` (callouts set this), or another reviewer's name (rendered dashed, as context).
- `sev`: `major`, `minor`, `nit`, `request`, `test`, `good`, `explain`.
- The line must be a new-file line inside some step's slice; the build exits 1 and names the item otherwise.
- `media` (optional): a list of `img` / `ab` / `video` blocks shown inside the finding card, so the screenshot or recording sits with the claim on its line. Notes (`steps[].notes`) take `media` too.

## Blocks

Used in `steps[].blocks` (main pane, after the prose) and `steps[].panel` (side panel).

| type | fields |
|---|---|
| `h` | `text` |
| `text` | `md` (paragraphs, lists, tables, `code`, **bold**) |
| `table` | `head?`, `rows` (cells are strings or `{v, tone: "ok"\|"bad"}`), `hl?` (row index to highlight) |
| `cards` | `items: [{l, v, tone?}]` |
| `json` | `value`, `strike?` (keys shown struck through, e.g. a field the next component never reads) |
| `lines` | `items: [{ts?, label, text, me?}]` — transcript or log lines; `me` highlights the record's own lines |
| `bars` | `items: [{label, value, main?}]`, `marker?: {value, label}` — e.g. totals against a threshold |
| `arch` | `boxes: [{title, tone, text, link?: {step, label}}]` — the overview's architecture strip |
| `asks` | `items: [{label, text, step}]` — clickable list that jumps to a step |
| `legend` | — the label and key legend |
| `drafts` | — tabs over `drafts` |
| `img` | `src`, `cap?`, `alt?`, `tag?` (small label above, e.g. "Desktop 1440"), `w?` (display width in px). Click opens a zoom overlay. |
| `ab` | `before: {src, cap?, tag?}`, `after: {…}`, `cap?` — two images side by side, stacked at phone width. Tags default to "Before" / "After"; use them for any pair (desktop/phone, step 1/step 2). |
| `video` | `src` (webm or mp4), `cap?`, `poster?` (an image; give one, or the first frame is often a loading state), `w?` |

### Media files

`src` is a path relative to the tour's directory (or `--media-root`), an absolute path, or an `https:`/`data:` URL. The build checks every local file exists (exit 1 if not), copies it to `<out dir>/media/<name>`, rewrites `src` to `media/<name>`, and prints the list. Names must be unique across the tour.

To publish, the Artifact tool takes supporting files only from the working directory or the session scratchpad: copy `<out dir>/media` to `<scratchpad>/tour-<pr>/media`, then publish the page with `root: <scratchpad>/tour-<pr>` and `files: ["media/<name>", …]`. Republishing the same page path keeps the URL; pass the media again when it changes.

## Minimal example

```json
{
  "id": "acme-412", "title": "Rate Limit Tour", "intent": "acme#412 · per-tenant rate limits on the public API",
  "repos": {"api": {"label": "API", "tone": "primary", "github": "acme/api"}},
  "lanes": [{"id": "client", "label": "Client", "tone": "external"}, {"id": "api", "label": "API", "tone": "primary"}, {"id": "redis", "label": "Redis", "tone": "external"}],
  "messages": [{"from": "client", "to": "api", "label": "request", "steps": ["middleware"]}, {"from": "api", "to": "redis", "label": "INCR tenant window", "steps": ["counter"]}],
  "glossary": [["Window", "The 60-second bucket a tenant's requests are counted in."]],
  "steps": [
    {"id": "overview", "section": "Start", "title": "What this change does", "prose": ["…"], "blocks": [{"type": "legend"}]},
    {"id": "middleware", "section": "The flow", "title": "Every request passes the limiter", "prose": ["…"], "slices": [{"h": "api-middleware-limit-1"}]},
    {"id": "verdicts", "section": "Decide", "title": "What we post", "blocks": [{"type": "drafts"}]}
  ],
  "findings": [], "callouts": [], "drafts": {"acme#412": "## Body\n…"}
}
```
