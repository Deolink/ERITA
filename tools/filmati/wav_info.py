"""Formato e profilo di volume di file WAV PCM (sola lettura)."""
import array
import math
import sys
import wave

WINDOW = 5  # secondi per colonna


def db(x):
    return 20 * math.log10(x / 32768) if x > 0 else -120.0


for path in sys.argv[1:]:
    with wave.open(path, "rb") as w:
        ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        print(f"== {path}")
        print(f"canali {ch}  {rate} Hz  {width * 8} bit  {n:,} campioni  {n / rate:.3f} s")
        if width != 2:
            print("  (profilo solo per PCM 16 bit)")
            continue
        per = rate * WINDOW
        cols = [[] for _ in range(ch)]
        peak = [0] * ch
        silent_from = None
        while True:
            raw = w.readframes(per)
            if not raw:
                break
            s = array.array("h", raw)
            for c in range(ch):
                part = s[c::ch]
                rms = math.sqrt(sum(v * v for v in part) / len(part))
                cols[c].append(rms)
                peak[c] = max(peak[c], max(abs(v) for v in part))
        for c in range(ch):
            print(f"  canale {c}: picco {db(peak[c]):6.1f} dBFS")
            print("   dB/5s: " + " ".join(f"{db(r):4.0f}" for r in cols[c]))
        print()
