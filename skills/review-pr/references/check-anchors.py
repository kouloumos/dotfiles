#!/usr/bin/env python3
"""Validate inline-review-comment anchors against a PR's diff, before you POST.

GitHub accepts a bad anchor and degrades it silently, and a pending review
reports back only `position` (never `line`/`side`/`subject_type`), so a
post-hoc check has to reverse-map and is easy to get wrong. Checking forwards
— "is this (path, line, side) inside a hunk?" — is the same direction as the
API call and fails before anything is created.

    check-anchors.py <owner>/<repo> <pr> src/a.ts:310 src/b.ts:71:RIGHT
    check-anchors.py <owner>/<repo> <pr> --list src/a.ts
    check-anchors.py <owner>/<repo> <pr> --pos  src/a.ts 59

Side defaults to RIGHT. Exit status is non-zero if any anchor is unusable.
"""
import json
import subprocess
import sys


def head_sha(repo, pr):
    return subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr}", "--jq", ".head.sha"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


def patches(repo, pr):
    """Always reflects the PR's CURRENT head — this endpoint takes no ref."""
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr}/files", "--paginate"],
        capture_output=True, text=True, check=True,
    ).stdout
    return {f["filename"]: f.get("patch", "") for f in json.loads(out)}


def anchors(patch):
    """position -> (side, line, text). Header is position 0; the line below it is 1."""
    out, pos, newno, oldno, first = {}, 0, None, None, True
    for ln in patch.split("\n"):
        if ln.startswith("@@"):
            head = ln.split("@@")[1]
            oldno = int(head.split("-")[1].split(",")[0])
            newno = int(head.split("+")[1].split(",")[0])
            if first:
                first = False
            else:
                pos += 1
            continue
        if newno is None:
            continue
        pos += 1
        if ln.startswith("-"):
            out[pos] = ("LEFT", oldno, ln)
            oldno += 1
        elif ln.startswith("+"):
            out[pos] = ("RIGHT", newno, ln)
            newno += 1
        else:  # context line: addressable on either side
            out[pos] = ("BOTH", newno, ln)
            newno += 1
            oldno += 1
    return out


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    repo, pr, rest = sys.argv[1], sys.argv[2], sys.argv[3:]

    expect = None
    if "--expect" in rest:
        i = rest.index("--expect")
        expect = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]

    head = head_sha(repo, pr)
    print(f"# checked against head {head}", file=sys.stderr)
    if expect and not head.startswith(expect.rstrip()):
        print(f"HEAD MOVED — you anchored against {expect}, the PR is now at {head}.\n"
              f"Re-read the diff and re-anchor; a staged review's line numbers are "
              f"commit-specific and will have shifted silently.", file=sys.stderr)
        sys.exit(2)

    files = patches(repo, pr)

    if rest[0] == "--list":
        path = rest[1]
        for pos, (side, line, text) in sorted(anchors(files.get(path, "")).items()):
            print(f"pos {pos:>4}  {side:<5} line {line:<5} {text[:70]}")
        return

    if rest[0] == "--pos":
        path, pos = rest[1], int(rest[2])
        got = anchors(files.get(path, "")).get(pos)
        print(f"{path} position {pos} -> {got}" if got else f"{path}: no position {pos}")
        return

    bad = 0
    for spec in rest:
        parts = spec.split(":")
        path, line = ":".join(parts[:-1]), parts[-1]
        side = "RIGHT"
        if not line.isdigit():  # path:line:SIDE
            path, line, side = ":".join(parts[:-2]), parts[-2], parts[-1].upper()
        line = int(line)
        if path not in files:
            print(f"UNUSABLE  {spec}  — file not in this PR's diff")
            bad += 1
            continue
        hit = [(p, s, t) for p, (s, l, t) in anchors(files[path]).items()
               if l == line and (s == side or s == "BOTH")]
        if hit:
            p, s, t = hit[0]
            print(f"ok        {path}:{line} {side}  (position {p})  {t[:60]}")
        else:
            print(f"UNUSABLE  {path}:{line} {side}  — not inside a diff hunk; "
                  f"move it or put the point in the review body")
            bad += 1
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
