"""Analisi in sola lettura delle tracce audio di un file Bink 2 (.bk2).

Uso:
    python -I bk2_tracks.py FILE.bk2              # intestazione + statistiche per traccia
    python -I bk2_tracks.py ORIGINALE.bk2 ALTRO.bk2   # confronto traccia per traccia

Layout (come nel demuxer bink di FFmpeg):
  firma(4) dimensione-8(4) n_frame(4) frame_max(4) ?(4) larghezza(4) altezza(4)
  fps_num(4) fps_den(4) flag_video(4) n_tracce(4) [extra(4) nelle revisioni recenti]
  n_tracce * max_decoded(4), n_tracce * (rate u16, flag u16), n_tracce * id(4)
  indice: (n_frame + 1) * offset(4), bit 0 = keyframe
  ogni frame: per traccia [dim(4) + dati], poi video.
"""
import hashlib
import struct
import sys

FLAG_16BIT = 0x4000
FLAG_STEREO = 0x2000
FLAG_DCT = 0x1000
PLAUSIBLE_RATES = {8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000}


def u32(b, o):
    return struct.unpack_from("<I", b, o)[0]


def parse_header(f):
    head = f.read(4096)
    sig = head[:4]
    if sig[:3] not in (b"KB2", b"BIK"):
        raise SystemExit(f"Firma inattesa: {sig!r}")
    n_frames = u32(head, 8)
    n_tracks = u32(head, 40)
    # Le revisioni recenti hanno un campo in piu' prima delle tracce: provare entrambe
    # e tenere quella in cui l'indice dei frame parte esattamente dopo l'intestazione.
    for extra in (4, 0):
        base = 44 + extra
        rates, ids = [], []
        o = base + 4 * n_tracks
        for i in range(n_tracks):
            rate, flags = struct.unpack_from("<HH", head, o + 4 * i)
            rates.append((rate, flags))
        o += 4 * n_tracks
        ids = [u32(head, o + 4 * i) for i in range(n_tracks)]
        index_start = o + 4 * n_tracks
        f.seek(index_start)
        first = u32(f.read(4), 0) & ~1
        expected = index_start + 4 * (n_frames + 1)
        if first == expected and all(r in PLAUSIBLE_RATES for r, _ in rates):
            max_decoded = [u32(head, base + 4 * i) for i in range(n_tracks)]
            f.seek(index_start)
            raw = f.read(4 * (n_frames + 1))
            offsets = struct.unpack(f"<{n_frames + 1}I", raw)
            return {
                "signature": sig.decode("latin-1"),
                "file_size": u32(head, 4) + 8,
                "frames": n_frames,
                "width": u32(head, 20),
                "height": u32(head, 24),
                "fps": u32(head, 28) / max(1, u32(head, 32)),
                "video_flags": u32(head, 36),
                "extra_field": extra == 4,
                "tracks": [
                    {"id": ids[i], "rate": rates[i][0], "flags": rates[i][1],
                     "max_decoded": max_decoded[i]}
                    for i in range(n_tracks)
                ],
                "offsets": offsets,
            }
    raise SystemExit("Impossibile interpretare l'intestazione (layout sconosciuto).")


def scan(path):
    """Restituisce intestazione, byte audio per traccia per frame, hash audio/video."""
    with open(path, "rb") as f:
        h = parse_header(f)
        n_tracks = len(h["tracks"])
        sizes = [[] for _ in range(n_tracks)]
        audio_hash = [hashlib.sha256() for _ in range(n_tracks)]
        video_hash = hashlib.sha256()
        offs = h["offsets"]
        for i in range(h["frames"]):
            start = offs[i] & ~1
            end = offs[i + 1] & ~1
            f.seek(start)
            frame = f.read(end - start)
            p = 0
            for t in range(n_tracks):
                size = u32(frame, p)
                p += 4
                sizes[t].append(size)
                audio_hash[t].update(frame[p:p + size])
                p += size
            video_hash.update(frame[p:])
    h["sizes"] = sizes
    h["audio_sha"] = [x.hexdigest()[:16] for x in audio_hash]
    h["video_sha"] = video_hash.hexdigest()[:16]
    return h


def describe(path, h):
    dur = h["frames"] / h["fps"]
    print(f"== {path}")
    print(f"firma {h['signature']}  {h['width']}x{h['height']}  {h['fps']:.3f} fps  "
          f"{h['frames']} frame  {dur:.1f} s  {h['file_size']:,} byte  "
          f"campo extra: {h['extra_field']}")
    print(f"hash video {h['video_sha']}")
    secs = max(1, int(dur))
    bucket = 10  # secondi per colonna nel profilo
    per_bucket = int(round(h["fps"] * bucket))
    print(f"\n{'ID':>10} {'Hz':>6} {'canali':>6} {'cod':>4} {'KB tot':>8} {'kbit/s':>7} "
          f"{'pacch.<=4B':>10}  hash audio")
    for t, tr in enumerate(h["tracks"]):
        s = h["sizes"][t]
        tot = sum(s)
        empty = sum(1 for x in s if x <= 4)
        ch = 2 if tr["flags"] & FLAG_STEREO else 1
        cod = "DCT" if tr["flags"] & FLAG_DCT else "RDFT"
        print(f"{tr['id']:>10} {tr['rate']:>6} {ch:>6} {cod:>4} {tot / 1024:>8.0f} "
              f"{tot * 8 / 1000 / secs:>7.1f} {empty:>10}  {h['audio_sha'][t]}"
              f"   (flag 0x{tr['flags']:04x})")
    # Profilo: KB per finestra di 10 s, normalizzato sul massimo della traccia.
    # Una traccia di sola voce ha "buchi" nelle pause; musica/effetti e' piu' uniforme.
    print(f"\nProfilo (KB ogni {bucket} s; '.' = sotto il 30% del picco della traccia)")
    for t, tr in enumerate(h["tracks"]):
        s = h["sizes"][t]
        cols = [sum(s[i:i + per_bucket]) / 1024 for i in range(0, len(s), per_bucket)]
        peak = max(cols) or 1
        line = " ".join(f"{c:4.0f}" if c >= 0.3 * peak else "   ." for c in cols)
        print(f"{tr['id']:>10} | {line}")


def compare(a, b):
    print("\n== Confronto")
    print(f"video: {'identico' if a['video_sha'] == b['video_sha'] else 'DIVERSO (ricodificato)'}"
          f"   frame {a['frames']} vs {b['frames']}")
    ids_b = {tr["id"]: i for i, tr in enumerate(b["tracks"])}
    for i, tr in enumerate(a["tracks"]):
        j = ids_b.get(tr["id"])
        if j is None:
            print(f"ID {tr['id']}: assente nel secondo file")
            continue
        tb = b["tracks"][j]
        same_fmt = (tr["rate"], tr["flags"]) == (tb["rate"], tb["flags"])
        same = a["audio_sha"][i] == b["audio_sha"][j]
        print(f"ID {tr['id']:>10}: audio {'identico' if same else 'DIVERSO'}"
              f"{'' if same_fmt else '  formato diverso: ' + str((tb['rate'], hex(tb['flags'])))}"
              f"  posizione {i} -> {j}")
    for tr in b["tracks"]:
        if tr["id"] not in {x["id"] for x in a["tracks"]}:
            print(f"ID {tr['id']}: presente solo nel secondo file")


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    results = [scan(p) for p in sys.argv[1:]]
    for p, h in zip(sys.argv[1:], results):
        describe(p, h)
        print()
    if len(results) == 2:
        compare(*results)


if __name__ == "__main__":
    main()
