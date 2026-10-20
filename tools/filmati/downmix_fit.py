"""Verifica se ID 4 (stereo) e' un downmix lineare di ID 0..3 (minimi quadrati).

Uso: python -I downmix_fit.py CARTELLA PREFISSO   (es. ... movie 10010010)
"""
import sys
import wave
from pathlib import Path

import numpy as np


def load(path):
    with wave.open(str(path), "rb") as w:
        ch, rate = w.getnchannels(), w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
    return data.reshape(-1, ch).T / 32768.0, rate


folder, prefix = Path(sys.argv[1]), sys.argv[2]
tr = {i: load(folder / f"{prefix}_id{i}.wav")[0] for i in range(5)}
n = min(t.shape[1] for t in tr.values())
names = ["0.L", "0.R", "1.C", "2.LFE", "3.L", "3.R"]
X = np.vstack([tr[0][0], tr[0][1], tr[1][0], tr[2][0], tr[3][0], tr[3][1]])[:, :n].T


def db(x):
    return 10 * np.log10(x) if x > 0 else -999


for side, y in (("L", tr[4][0][:n]), ("R", tr[4][1][:n])):
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ coef
    print(f"ID4.{side} = " + "  ".join(f"{c:+.3f}*{nm}" for c, nm in zip(coef, names)))
    print(f"   residuo {db(np.mean(res**2) / np.mean(y**2)):.1f} dB rispetto al segnale")
    # Residuo per finestre di 5 s: se resta basso ovunque, il modello vale per tutto il filmato.
    w = 48000 * 5
    seg = [db(np.mean(res[i:i + w] ** 2) / max(np.mean(y[i:i + w] ** 2), 1e-12))
           for i in range(0, n - w + 1, w)]
    print("   residuo/5s dB: " + " ".join(f"{s:4.0f}" for s in seg))
    # Voce: quanta parte di ID4 resta correlata a ID1 dopo aver tolto la stima senza voce.
    no_voice = np.delete(X, 2, axis=1) @ np.delete(coef, 2)
    left = y - no_voice
    cv = np.corrcoef(left, X[:, 2])[0, 1]
    print(f"   correlazione con ID1 di (ID4 - parte senza voce): {cv:.3f}")
