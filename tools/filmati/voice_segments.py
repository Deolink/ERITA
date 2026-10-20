"""Trova i tratti in cui c'e' voce in una traccia mono (soglia RMS su finestre da 20 ms)."""
import sys
import wave

import numpy as np

THRESH_DB = -45.0
MIN_GAP = 0.6  # pause piu' corte uniscono due tratti
MIN_LEN = 0.25

with wave.open(sys.argv[1], "rb") as w:
    rate = w.getframerate()
    x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64) / 32768
win = rate // 50
n = len(x) // win
rms = np.sqrt(np.mean(x[: n * win].reshape(n, win) ** 2, axis=1))
active = 20 * np.log10(np.maximum(rms, 1e-9)) > THRESH_DB
segs = []
start = None
for i, a in enumerate(active):
    t = i * win / rate
    if a and start is None:
        start = t
    if not a and start is not None:
        segs.append([start, t])
        start = None
if start is not None:
    segs.append([start, n * win / rate])
merged = []
for s in segs:
    if merged and s[0] - merged[-1][1] < MIN_GAP:
        merged[-1][1] = s[1]
    else:
        merged.append(s)
merged = [s for s in merged if s[1] - s[0] >= MIN_LEN]


def tc(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:06.3f}"


for i, (a, b) in enumerate(merged, 1):
    print(f"{i}\t{tc(a)}\t{tc(b)}\t{b - a:.1f}")
