#!/usr/bin/env python3
"""Carve files from a raw disk image by content signature.

Use when the filesystem metadata (partition table / FAT / directory) is
destroyed but file *data* still survives on the media. Recovers file CONTENTS
only -- original names and folder structure are gone (use exfat.py first if the
directory tree is intact). Output files are named by their byte offset.

  carve.py scan  <image>                      inventory signatures by type
  carve.py carve <image> <outdir> [types...]  extract + validate (default: png jpeg pdf)
  carve.py dims  <dir>                         report image dimensions (triage
                                               screenshots vs thumbnails/icons)

Works via mmap, so it streams an 8GB+ image without loading it into RAM.
Fragmented files (data split across non-contiguous clusters) can't be fully
reassembled without the FAT: PNG/JPEG recover their leading portion (top of the
image still renders); a truncated PDF/other may be unusable. That is a physical
limit -- no carver beats it.
"""
import sys, os, struct, mmap

# --- signature carvers: each returns end offset (exclusive) or None ---

def carve_png(mm, s, n):
    i = s + 8                                   # past 8-byte signature
    while i + 8 <= n:
        ln = struct.unpack(">I", mm[i:i+4])[0]
        typ = mm[i+4:i+8]
        i += 12 + ln                            # len(4)+type(4)+data+crc(4)
        if typ == b"IEND":
            return i
        if ln > 100_000_000:
            return None
    return None

def carve_jpeg(mm, s, n):
    i = s + 2
    while i + 1 < n:
        if mm[i] == 0xFF:
            m = mm[i+1]
            if m == 0xD9:                       # EOI
                return i + 2
            if m in (0xD8, 0x01) or 0xD0 <= m <= 0xD7:
                i += 2; continue                # standalone markers, no length
            if 0xC0 <= m <= 0xFE:
                ln = struct.unpack(">H", mm[i+2:i+4])[0]
                i += 2 + ln; continue
        i += 1
        if i - s > 100_000_000:
            return None
    return None

def carve_pdf(mm, s, next_s, n):
    hi = next_s if next_s != -1 else n
    hi = min(hi, s + 64*1024*1024)              # cap: PDFs rarely exceed this
    pos = mm.rfind(b"%%EOF", s, hi)
    if pos == -1:
        return None
    end = pos + 5
    while end < n and mm[end:end+1] in (b"\r", b"\n"):
        end += 1
    return end

SIGS = {
    "png":  (b"\x89PNG\r\n\x1a\n", carve_png),
    "jpeg": (b"\xff\xd8\xff",      carve_jpeg),
    "pdf":  (b"%PDF-",             carve_pdf),
}
EXT = {"png": "png", "jpeg": "jpg", "pdf": "pdf"}

def find_all(mm, sig):
    offs = []; i = mm.find(sig)
    while i != -1:
        offs.append(i); i = mm.find(sig, i+1)
    return offs

def validate(path):
    sz = os.path.getsize(path)
    with open(path, "rb") as f:
        head = f.read(16); f.seek(max(0, sz-16)); tail = f.read(16)
    if path.endswith(".png"):
        return head.startswith(b"\x89PNG") and tail.endswith(b"IEND\xaeB`\x82")
    if path.endswith(".jpg"):
        return head.startswith(b"\xff\xd8\xff") and tail.endswith(b"\xff\xd9")
    if path.endswith(".pdf"):
        return head.startswith(b"%PDF") and b"%%EOF" in tail
    return None

def open_mm(image):
    f = open(image, "rb")
    return f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

def cmd_scan(image):
    f, mm = open_mm(image); n = mm.size()
    print(f"image: {image}  ({n:,} bytes)\n")
    for t, (sig, _) in SIGS.items():
        offs = find_all(mm, sig)
        print(f"  {t:<6} {len(offs):>6} signatures   first: {offs[:4]}")
    mm.close(); f.close()

def cmd_carve(image, outdir, types):
    os.makedirs(outdir, exist_ok=True)
    f, mm = open_mm(image); n = mm.size()
    saved = {}
    for t in types:
        sig, fn = SIGS[t]; offs = find_all(mm, sig); ok = 0
        for idx, s in enumerate(offs):
            if t == "pdf":
                nxt = offs[idx+1] if idx+1 < len(offs) else -1
                e = fn(mm, s, nxt, n)
            else:
                e = fn(mm, s, n)
            if e and e - s > 100:
                p = os.path.join(outdir, f"{t}_{s}.{EXT[t]}")
                with open(p, "wb") as o:
                    o.write(mm[s:e])
                ok += 1
        saved[t] = ok
    mm.close(); f.close()
    total = valid = 0
    for fn_ in sorted(os.listdir(outdir)):
        p = os.path.join(outdir, fn_); v = validate(p)
        total += 1; valid += 1 if v else 0
    print(f"carved: {saved} -> {outdir}")
    print(f"validated: {valid}/{total} pass header+trailer checks "
          f"(failures are usually fragmented -- may still partly render)")

def cmd_dims(d):
    """Report PNG/JPEG dimensions so you can tell screenshots/photos (large)
    from thumbnails/icons (small). Reads IHDR/SOF headers directly, no deps."""
    rows = []
    for fn in os.listdir(d):
        p = os.path.join(d, fn)
        try:
            with open(p, "rb") as f:
                b = f.read(32)
            if b.startswith(b"\x89PNG") and b[12:16] == b"IHDR":
                w, h = struct.unpack(">II", b[16:24]); rows.append((w, h, fn))
            elif b.startswith(b"\xff\xd8\xff"):
                with open(p, "rb") as f:
                    data = f.read()
                i = 2
                while i + 9 < len(data):
                    if data[i] == 0xFF and 0xC0 <= data[i+1] <= 0xC3:
                        h, w = struct.unpack(">HH", data[i+5:i+9]); rows.append((w, h, fn)); break
                    if data[i] == 0xFF and data[i+1] not in (0xD8,0x01) and not 0xD0<=data[i+1]<=0xD7:
                        i += 2 + struct.unpack(">H", data[i+2:i+4])[0]; continue
                    i += 1
        except Exception:
            pass
    rows.sort(key=lambda r: -(r[0]*r[1]))
    print(f"{'width':>6} {'height':>6}  file   (largest first -- screenshots/photos on top)")
    for w, h, fn in rows:
        big = "  <-- large (screenshot/photo?)" if (w >= 1000 or h >= 1000) else ""
        print(f"{w:>6} {h:>6}  {fn}{big}")

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "scan":
        cmd_scan(sys.argv[2])
    elif cmd == "carve":
        types = sys.argv[4:] or ["png", "jpeg", "pdf"]
        cmd_carve(sys.argv[2], sys.argv[3], types)
    elif cmd == "dims":
        cmd_dims(sys.argv[2])
    else:
        print(__doc__); sys.exit(1)

if __name__ == "__main__":
    main()
