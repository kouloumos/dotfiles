# Runtime probes for PR review

Techniques for Phase 3 (Runtime Verification). All of these run through the `browser-scripting` skill — `playwright-run script.mjs`, with `const pw = await import(process.env.PLAYWRIGHT)`.

Read this when you are about to write a verification script and want a pattern that already works, or when a probe is giving results you don't trust.

## Baseline A/B inventory — the highest-value probe

Drives identical steps against two deployments and diffs the observable state. This is what finds behaviour nobody proposed as a hypothesis.

The core is a `inventory()` that classifies rendered elements by *kind* rather than counting them, so the diff is readable:

```js
const inventory = (page) => page.evaluate(() => {
  const ms = [...document.querySelectorAll('.some-marker-class, [data-testid]')];
  const kind = (el) => { /* classify by class, aria-label, role, size */ };
  const tally = {};
  for (const m of ms) { const k = kind(m); tally[k] = (tally[k] || 0) + 1; }
  return { total: ms.length, tally, dialogs: document.querySelectorAll('[role=dialog]').length };
});
```

Then a `step(name, action)` helper that acts, waits, and records; run the same sequence against both URLs; print `same`/`DIFF` per step with both tallies on a diff.

Two things that make or break it:

- **Choose the steps from existing user flows that pass through changed code**, not from the new feature. The new feature has no baseline.
- **Include a control step** you expect to be identical. If your control differs, your classifier is wrong, not the app. (A step showing "11 donuts" vs "11 packed-donuts" is a classifier artifact, not a finding — the wrapper changed, the behaviour didn't.)

If the base isn't deployed anywhere, run it locally on a second port or in a second worktree.

## Hit-area / click-routing probe

Finds elements whose clickable box doesn't match their painted pixels — invisible boxes swallowing clicks, or one control capturing another's.

For each element, sample points across the region a user would aim at, and ask what `elementFromPoint` actually returns:

```js
const hit = document.elementFromPoint(x, y)?.closest('.owner-selector');
if (hit && hit !== ownerEl) steals.push({ over: name(ownerEl), goesTo: name(hit) });
```

Sample the *painted* region (e.g. the logo disc), not the bounding box — a hit on a transparent corner is not necessarily a bug, a hit on top of a neighbour's ink is. Report the affected area as a fraction of sampled points and as pixels, so severity is measured rather than asserted.

To prove it end-to-end, install a capture-phase listener that records which owner receives a real click, then dispatch one:

```js
window.addEventListener('click', (e) => { window.__got = e.target.closest('.owner-selector'); }, true);
```

## Rendering computed values into the page and measuring them

When the claim is about a *computed* visual property (contrast, size, spacing) across a range, don't reason about it — render the whole range into the live page with the real CSS and measure with `getComputedStyle`. This catches both product bugs and errors in your own arithmetic.

**Gotcha that will silently invalidate results:** modern Chrome returns resolved colours as `color(srgb 0.908 0.908 0.908)` — floats in 0–1, not 0–255. Parse both forms:

```js
const px = s => { const n = s.match(/[\d.]+/g).map(Number);
  return s.includes('color(') ? n.slice(0,3).map(x => x*255) : n.slice(0,3); };
```

Getting this wrong makes every contrast ratio come out ≈1.0. If a measurement looks impossibly uniform, suspect the parser before the product.

Sample the **whole reachable domain**, not a lattice. A loop over `intensity += 0.1` can step clean over a narrow failing band that a loop over every integer percentage would catch.

## Snapshot → act → snapshot deltas

For layout-stability claims ("this doesn't move when you pan", "nothing re-renders on X"): snapshot the positions, perform the action, snapshot again, and compare each element's delta against the *median* delta. Anything deviating from the common movement vector moved for its own reasons.

```js
const med = f => rows.map(r => r[f]).sort((a,b)=>a-b)[Math.floor(rows.length/2)];
rows.forEach(r => r.deviation = Math.hypot(r.dx - med('dx'), r.dy - med('dy')));
```

Run it several times with different magnitudes — a property can hold for one input and fail for another. Integer coordinates in particular can hide floating-point instability that real projected values expose.

## A/B with a working control

When a finding is "path X is broken", find a path Y with the same user intent that works, and capture both. An asymmetry is far harder to dismiss than a claim, and it localises the fix. Build the comparison as one artifact with both panels labelled.

## Artifacts

Capture at the moment of reproduction — never plan to reproduce it later for the screenshot.

- Annotate geometric defects before capturing: draw element boxes, mark affected points, then clip tight at `deviceScaleFactor: 2`–`3`.
- Use `recordVideo` on the context for interaction and animation defects a still can't show. Convert to `.mp4` (`ffmpeg -c:v libx264 -pix_fmt yuv420p -movflags +faststart`) — GitHub renders mp4/mov as a player.
- Compose A/B pairs into a single labelled image: `setContent` with both screenshots as base64 `<img>` and a caption bar each, then screenshot that page.
- **Check the artifact actually shows the defect.** A camera that flew elsewhere, a popup anchored off-screen, or a collapsed panel can produce a technically-correct screenshot that demonstrates nothing. If the evidence isn't visible in the frame, adjust the state (zoom out, scroll) until it is.

## General gotchas

- Map and live-updating pages never reach `networkidle` — use `domcontentloaded` plus explicit waits.
- Dev servers compile on first hit; wait for the compile overlay to clear before capturing.
- Dismiss cookie/consent banners before A/B captures, or the two panels won't be comparable.
- Some "cards" are `div[role=button]`, not `<button>` — inspect the DOM chain rather than guessing the selector.
- After an action that moves a camera or collapses a panel, the element you interacted with may be unmounted or off-screen; prefer `el.evaluate(e => e.click())` over `.click()` when the target may have scrolled out of the viewport.
