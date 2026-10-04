#!/usr/bin/env python3
"""Split one or more PR diffs into a hunk inventory (hunks.json).

Deterministic part of the tour's inventory: every hunk of every diff, with its
exact text and line ranges. The inventory agent then annotates each hunk
(role, chapter, description, key, focus) — see inventory-prompt.md.

Usage:
  make_hunks.py --repo KEY=PATH:BASE:HEAD[:OWNER/NAME] [--repo ...] -o hunks.json

  KEY        short id used everywhere in the tour ("app", "tasks", "api")
  PATH       local checkout of the repo
  BASE/HEAD  commits to diff (BASE is usually `git merge-base origin/main HEAD`)
  OWNER/NAME GitHub repo, for links (optional)
"""
import argparse, json, os, re, subprocess

def hunks_of(key, path, base, head):
    diff = subprocess.run(["git", "-C", path, "diff", "-U3", "--no-color", base, head],
                          capture_output=True, text=True, check=True).stdout
    out, cur_file, counter = [], None, {}
    lines = diff.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("diff --git"):
            cur_file = None
        elif ln.startswith("+++ "):
            cur_file = ln[6:] if ln.startswith("+++ b/") else None
        elif ln.startswith("--- ") and cur_file is None:
            pass
        elif ln.startswith("@@") and cur_file:
            m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", ln)
            body = [ln]
            i += 1
            while i < len(lines) and not lines[i].startswith(("@@", "diff --git")):
                body.append(lines[i]); i += 1
            new_start, new_len = int(m.group(3)), int(m.group(4) or 1)
            stem = re.sub(r"[^A-Za-z0-9.]+", "-", "-".join(cur_file.split("/")[-2:]).rsplit(".", 1)[0]).strip("-")
            counter[stem] = counter.get(stem, 0) + 1
            out.append({
                "id": f"{key}-{stem}-{counter[stem]}", "repo": key, "path": cur_file, "header": ln,
                "newStart": new_start, "newEnd": new_start + max(new_len, 1) - 1,
                "added": sum(1 for b in body[1:] if b.startswith("+")),
                "removed": sum(1 for b in body[1:] if b.startswith("-")),
                "text": "\n".join(body),
                # filled by the inventory agent:
                "role": None, "chapter": None, "key": False, "focus": [], "description": None,
            })
            continue
        i += 1
    return out

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    repos, hunks = {}, []
    for spec in a.repo:
        key, rest = spec.split("=", 1)
        parts = rest.split(":")
        path, base, head = parts[0], parts[1], parts[2]
        gh = parts[3] if len(parts) > 3 else None
        head_full = subprocess.run(["git", "-C", path, "rev-parse", head], capture_output=True, text=True, check=True).stdout.strip()
        repos[key] = {"path": os.path.abspath(path), "base": base, "head": head_full, "github": gh}
        hunks += hunks_of(key, path, base, head)
    json.dump({"repos": repos, "hunks": hunks}, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(f"{len(hunks)} hunks, {sum(h['added'] + h['removed'] for h in hunks)} changed lines -> {a.out}")
