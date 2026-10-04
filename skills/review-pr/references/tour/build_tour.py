#!/usr/bin/env python3
"""Build a guided diff tour page from tour.json + hunks.json.

  build_tour.py --tour tour.json --hunks hunks.json -o index.html

tour.json is authored per review (schema: tour-schema.md). hunks.json comes
from make_hunks.py and is annotated by the inventory agent. The build:
  - resolves each step's slices (a hunk, or a new-line range of a hunk);
  - collects every changed line no step showed into two closing steps
    ("unfocused parts of new files" for core/test/guard hunks, "safe to skip"
    for the rest), so the tour covers the whole diff by construction;
  - places each finding and callout on a shown line (or reports it unplaced);
  - injects the data into template.html (next to this script).
Exit code 1 if a slice names an unknown hunk or a finding cannot be placed.
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def lines_of(h):
    m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", h["text"].splitlines()[0])
    o, n, out = int(m.group(1)), int(m.group(2)), []
    for raw in h["text"].splitlines()[1:]:
        if raw.startswith("\\"):
            continue
        k, t = raw[:1], raw[1:]
        if k == "+":
            out.append(["+", None, n, t]); n += 1
        elif k == "-":
            out.append(["-", o, None, t]); o += 1
        else:
            out.append([" ", o, n, t]); o += 1; n += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", required=True); ap.add_argument("--hunks", required=True); ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    tour = json.load(open(a.tour)); inv = json.load(open(a.hunks))
    H = {h["id"]: h for h in inv["hunks"]}
    seen_new, seen_del, errors = {}, {}, []

    def take(h, r):
        sel, last_new = [], None
        for k, o, n, t in lines_of(h):
            if not r:
                sel.append([k, o, n, t])
            elif n is not None:
                last_new = n
                if r[0] <= n <= r[1]:
                    sel.append([k, o, n, t])
            elif last_new is not None and r[0] <= last_new + 1 <= r[1] + 1:
                sel.append([k, o, n, t])
        for k, o, n, t in sel:
            if n is not None: seen_new.setdefault(h["id"], set()).add(n)
            else: seen_del.setdefault(h["id"], set()).add(o)
        return sel

    def slice_of(h, r=None, cap=None, collapsed=False):
        return {"hunk": h["id"], "repo": h["repo"], "path": h["path"], "role": h.get("role"),
                "caption": cap or h.get("description") or h["path"], "collapsed": collapsed, "lines": take(h, r)}

    steps = []
    for st in tour["steps"]:
        out = dict(st); out["slices"] = []
        for s in st.get("slices", []):
            if s["h"] not in H:
                errors.append(f"step {st['id']}: unknown hunk {s['h']}"); continue
            out["slices"].append(slice_of(H[s["h"]], s.get("r"), s.get("cap"), s.get("collapsed", False)))
        out.setdefault("notes", []); out.setdefault("checks", []); out.setdefault("prose", [])
        steps.append(out)

    # leftovers: every changed line no step showed
    rest_new, rest_skip = [], []
    for h in inv["hunks"]:
        left = [l for l in lines_of(h) if (l[0] == "+" and l[2] not in seen_new.get(h["id"], set())) or (l[0] == "-" and l[1] not in seen_del.get(h["id"], set()))]
        if not left:
            continue
        news = [l[2] for l in left if l[2] is not None]
        r = [min(news), max(news)] if news else [h["newStart"], h["newEnd"]]
        sl = slice_of(h, r, None, True)
        (rest_new if h.get("role") in ("core", "test", "guard") else rest_skip).append(sl)
    tail = tour.get("tailSteps", {})
    closing = [
        {"id": "rest-new", "section": tail.get("section", "The rest"), "title": "The unfocused parts of new files", "prose": [tail.get("restNew", "Parts of new or large files that no step focused on.")], "slices": rest_new},
        {"id": "rest", "section": tail.get("section", "The rest"), "title": "Everything else: safe to skip", "prose": [tail.get("rest", "Wiring, config and docs that no step showed. With this step, every changed line is in the tour.")], "slices": rest_skip},
    ]
    insert_at = next((i for i, s in enumerate(steps) if s.get("id") == "verdicts"), len(steps))
    for c in closing:
        if c["slices"]:
            c.update({"notes": [], "checks": [], "where": []}); steps.insert(insert_at, c); insert_at += 1

    # findings and callouts onto shown lines
    anchored = [dict(f) for f in tour.get("findings", [])] + [{"repo": c[0], "path": c[1], "line": c[2], "who": "explain", "sev": "explain", "title": c[3], "text": ""} for c in tour.get("callouts", [])]
    for f in anchored:
        placed = False
        for st in steps:
            for sl in st["slices"]:
                if sl["repo"] == f["repo"] and sl["path"] == f["path"] and any(l[2] == f["line"] for l in sl["lines"]):
                    sl.setdefault("findings", []).append(f); placed = True; break
            if placed: break
        if not placed:
            errors.append(f"unplaced {f.get('who')} item at {f['repo']}:{f['path']}:{f['line']} — '{f.get('title', '')[:60]}'")

    data = {k: v for k, v in tour.items() if k not in ("steps", "findings", "callouts")}
    data["steps"] = steps
    data["repos"] = {k: {**tour.get("repos", {}).get(k, {}), "head": inv["repos"][k]["head"], "github": tour.get("repos", {}).get(k, {}).get("github") or inv["repos"][k].get("github")} for k in inv["repos"]}
    page = open(os.path.join(HERE, "template.html")).read()
    page = page.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    page = page.replace("<title>Guided Review Tour</title>", f"<title>{tour.get('title', 'Guided Review Tour')}</title>", 1)
    open(a.out, "w").write(page)
    changed = sum(h["added"] + h["removed"] for h in inv["hunks"])
    print(f"{len(steps)} steps, {sum(len(s['slices']) for s in steps)} slices, {changed} changed lines, {len(anchored)} anchored items, {len(page) // 1024} KB -> {a.out}")
    for e in errors:
        print("ERROR:", e, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
