"""Confronta campi d'intestazione e dimensioni dei frame di due .bk2 (sola lettura).

Uso: python -I bk2_header_diff.py ORIGINALE.bk2 MODIFICATO.bk2
"""
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bk2_tracks  # noqa: E402


def fields(path):
    with open(path, "rb") as f:
        head = f.read(64)
        f.seek(0)
        h =bk2_tracks.parse_header(f)
    names = ["firma", "dim-8", "frame", "frame_max", "?16", "larg", "alt", "fps_n", "fps_d",
             "flag_video", "n_tracce", "extra"]
    vals = struct.unpack_from("<4s11I", head, 0)
    offs = h["offsets"]
    sizes = [(offs[i + 1] & ~1) - (offs[i] & ~1) for i in range(h["frames"])]
    keys = [o & 1 for o in offs[:-1]]
    return dict(zip(names, vals)), h, sizes, keys


a, ha, sa, ka = fields(sys.argv[1])
b, hb, sb, kb = fields(sys.argv[2])
print("Campi d'intestazione:")
for k in a:
    mark = "" if a[k] == b[k] else "   <-- diverso"
    print(f"  {k:>10}: {a[k]!s:>14} {b[k]!s:>14}{mark}")
print("\nPer traccia (ID, max_decoded):")
for t in ha["tracks"]:
    tb = next(x for x in hb["tracks"] if x["id"] == t["id"])
    print(f"  ID {t['id']}: {t['max_decoded']:>8} -> {tb['max_decoded']:>8}")
print(f"\nframe piu' grande reale: {max(sa):,} -> {max(sb):,}"
      f"  (dichiarato {a['frame_max']:,} -> {b['frame_max']:,})")
print(f"keyframe identici: {ka == kb}   ({sum(ka)} keyframe)")
diff = [y - x for x, y in zip(sa, sb)]
print(f"frame con dimensione diversa: {sum(1 for d in diff if d)} su {len(diff)}")
print(f"differenza totale: {sum(diff):+,} byte "
      f"(file {a['dim-8'] + 8:,} -> {b['dim-8'] + 8:,}, {b['dim-8'] - a['dim-8']:+,})")
