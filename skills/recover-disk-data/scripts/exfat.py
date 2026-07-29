#!/usr/bin/env python3
"""Recover files from an exFAT image whose directory tree survives.

Use when a partition table / boot sector was wiped but the exFAT filesystem body
is intact -- recovers files WITH their original names and folder structure.
Auto-locates the exFAT boot sector (it searches for the 'EXFAT   ' signature, so
it works even if the primary boot sector at the volume start was destroyed and
only a backup copy remains). The FAT is NOT required: files are read assuming
contiguous allocation (exFAT 'NoFatChain'); non-contiguous files are flagged.

  exfat.py find    <image>              locate boot sector(s) + print geometry
  exfat.py list    <image>              walk the directory tree (names/sizes/flags)
  exfat.py extract <image> <outdir>     copy files out, preserving structure

If `list` shows garbage or wrong data, the directory is stale relative to the
current data (the volume was rewritten) -- fall back to carve.py (by content).
"""
import sys, os, struct, mmap

def open_mm(image):
    f = open(image, "rb")
    return f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)

def find_boot_sectors(mm):
    """Yield (offset, geometry-dict) for every valid exFAT boot sector."""
    out = []; i = mm.find(b"EXFAT   ")
    while i != -1:
        bs_off = i - 3                                   # 'EXFAT   ' sits at boot+3
        if bs_off >= 0 and mm[bs_off:bs_off+3] == b"\xeb\x76\x90" and mm[bs_off+510:bs_off+512] == b"\x55\xaa":
            bs = mm[bs_off:bs_off+512]
            g = dict(
                boot_off      = bs_off,
                part_off      = struct.unpack("<Q", bs[64:72])[0],
                vol_len       = struct.unpack("<Q", bs[72:80])[0],
                fat_off       = struct.unpack("<I", bs[80:84])[0],
                heap_off      = struct.unpack("<I", bs[88:92])[0],
                clus_cnt      = struct.unpack("<I", bs[92:96])[0],
                root_clus     = struct.unpack("<I", bs[96:100])[0],
                bps           = 1 << bs[108],
                spc           = 1 << bs[109],
            )
            out.append(g)
        i = mm.find(b"EXFAT   ", i+1)
    return out

def geom_offsets(g):
    """Absolute byte offsets, treating the image as a whole disk (volume starts
    at part_off sectors from image start)."""
    bps, spc = g["bps"], g["spc"]
    vol = g["part_off"] * bps
    cluster = spc * bps
    def cluster_off(c):
        return vol + (g["heap_off"] + (c-2) * spc) * bps
    return vol, cluster, cluster_off

def read_dir_bytes(mm, cluster_off, cluster, first_c, max_bytes, cluscnt):
    out = bytearray(); c = first_c
    limit = max_bytes if max_bytes else 256 * cluster
    while len(out) < limit and 2 <= c <= cluscnt + 1:
        chunk = mm[cluster_off(c):cluster_off(c)+cluster]
        out += chunk
        if chunk[:1] == b"\x00":
            break
        c += 1
    return bytes(out)

def parse_dir(data):
    i = 0; n = len(data)
    while i + 32 <= n:
        t = data[i]
        if t == 0x00:
            break
        if t == 0x85:
            sc = data[i+1]; attrs = struct.unpack("<H", data[i+4:i+6])[0]
            st = data[i+32:i+64]
            if len(st) < 32 or st[0] != 0xC0:
                i += 32; continue
            no_fat = bool(st[1] & 0x02)
            fc = struct.unpack("<I", st[20:24])[0]
            dl = struct.unpack("<Q", st[24:32])[0]
            name = ""
            for k in range(sc-1):
                ne = data[i+64+k*32:i+96+k*32]
                if len(ne) < 32 or ne[0] != 0xC1:
                    break
                name += ne[2:32].decode("utf-16-le", "replace")
            name = name[:st[3]]
            yield dict(name=name, is_dir=bool(attrs & 0x10), fc=fc, size=dl, contiguous=no_fat)
            i += 32 * (1 + sc)
        else:
            i += 32

def walk(mm, g, cluster_off, cluster, first_c, size, path, out, extract_dir, stats, visited, depth):
    cc = g["clus_cnt"]
    if depth > 100 or first_c in visited or not (2 <= first_c <= cc+1):
        return
    visited.add(first_c)
    data = read_dir_bytes(mm, cluster_off, cluster, first_c, size, cc)
    for r in parse_dir(data):
        nm = r["name"]
        if nm in ("", ".", ".."):
            continue
        if not (2 <= r["fc"] <= cc+1):
            continue
        full = f"{path}/{nm}"
        if r["is_dir"]:
            out.append(("DIR ", full, r["size"], True))
            if extract_dir:
                os.makedirs(os.path.join(extract_dir, full.lstrip("/")), exist_ok=True)
            walk(mm, g, cluster_off, cluster, r["fc"], r["size"], full, out, extract_dir, stats, visited, depth+1)
        else:
            out.append(("FILE", full, r["size"], r["contiguous"]))
            stats["files"] += 1; stats["bytes"] += r["size"]
            if not r["contiguous"]:
                stats["frag"] += 1
            if extract_dir:
                dest = os.path.join(extract_dir, full.lstrip("/"))
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                rem = r["size"]; c = r["fc"]
                with open(dest, "wb") as o:
                    while rem > 0 and 2 <= c <= cc+1:
                        chunk = mm[cluster_off(c):cluster_off(c)+min(cluster, rem)]
                        if not chunk:
                            break
                        o.write(chunk); rem -= len(chunk); c += 1

def pick_geometry(mm):
    boots = find_boot_sectors(mm)
    if not boots:
        return None, []
    # prefer a boot sector whose root directory validates (0x83/0x81/0x82 entries)
    for g in boots:
        vol, cluster, cluster_off = geom_offsets(g)
        root = mm[cluster_off(g["root_clus"]):cluster_off(g["root_clus"])+96]
        if root[:1] in (b"\x83", b"\x81", b"\x82"):
            return g, boots
    return boots[0], boots

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    cmd, image = sys.argv[1], sys.argv[2]
    f, mm = open_mm(image)
    if cmd == "find":
        boots = find_boot_sectors(mm)
        print(f"{len(boots)} exFAT boot sector(s) in {image}:\n")
        for g in boots:
            vol, cluster, cluster_off = geom_offsets(g)
            root = mm[cluster_off(g["root_clus"]):cluster_off(g["root_clus"])+16]
            valid = root[:1] in (b"\x83", b"\x81", b"\x82")
            print(f"  boot@{g['boot_off']:>12}  part_off={g['part_off']} sec  vol_start={vol}  "
                  f"cluster={cluster}B  root_clus={g['root_clus']}")
            print(f"      root dir first bytes: {root.hex()}  "
                  f"({'VALID volume label/bitmap -- data intact here' if valid else 'not a dir header -- stale/destroyed'})")
        mm.close(); f.close(); return
    g, boots = pick_geometry(mm)
    if not g:
        print("No exFAT boot sector found -- filesystem type may differ, or use carve.py"); mm.close(); f.close(); return
    vol, cluster, cluster_off = geom_offsets(g)
    extract_dir = sys.argv[3] if cmd == "extract" and len(sys.argv) > 3 else None
    if extract_dir:
        os.makedirs(extract_dir, exist_ok=True)
    out = []; stats = {"files": 0, "bytes": 0, "frag": 0}
    walk(mm, g, cluster_off, cluster, g["root_clus"], 0, "", out, extract_dir, stats, set(), 0)
    for kind, path, size, contig in out:
        flag = "" if contig or kind == "DIR " else "  [!FRAGMENTED tail may be corrupt]"
        print(f"{kind} {size:>12,}  {path}{flag}")
    print(f"\nfiles: {stats['files']:,}   bytes: {stats['bytes']:,} ({stats['bytes']/1e9:.2f} GB)   "
          f"fragmented: {stats['frag']}")
    if extract_dir:
        print(f"extracted -> {extract_dir}")
    mm.close(); f.close()

if __name__ == "__main__":
    main()
