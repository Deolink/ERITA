"""Genera l'ID4 stereo senza voce inglese (o con la voce nuova), in due modi.

  A = ricostruzione: downmix di ID0 + ID2 + ID3 (+ voce nuova) con i coefficienti stimati
  B = sottrazione:   ID4 originale - g*ID1 (+ g*voce nuova)

Con VOCE_NUOVA.wav scrive anche l'ID1 pronto per "Mix in sound": mono, alla stessa
frequenza e lunghezza dell'originale (una voce stereo viene mescolata in mono, una
voce piu' corta viene completata con silenzio; una voce piu' lunga e' un errore).
Se il risultato supererebbe 0 dBFS viene abbassato quanto basta per non saturare.

Uso: python -I make_id4.py CARTELLA_WAV PREFISSO CARTELLA_OUT [VOCE_NUOVA.wav]
I WAV di origine si chiamano PREFISSO_id0.wav ... PREFISSO_id4.wav.
"""
import sys
import wave
from pathlib import Path

import numpy as np

FULL_SCALE = 32767 / 32768  # oltre questo valore il PCM a 16 bit satura
HEADROOM = 0.989  # se serve abbassare, si porta il picco a circa -0.1 dBFS


def load(path):
    with wave.open(str(path), "rb") as w:
        ch, rate, width = w.getnchannels(), w.getframerate(), w.getsampwidth()
        if width != 2:
            raise SystemExit(f"{path}: serve PCM a 16 bit, trovato {width * 8} bit.")
        d = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float64)
    return d.reshape(-1, ch).T / 32768.0, rate


def save(path, channels, rate):
    channels = np.atleast_2d(channels)
    peak = float(np.max(np.abs(channels)))
    if np.max(channels) > FULL_SCALE or np.min(channels) < -1.0:
        channels = channels * (HEADROOM / peak)
        print(f"  abbassato di {20 * np.log10(HEADROOM / peak):.2f} dB per evitare la saturazione")
    pcm = np.clip(np.round(channels.T * 32768.0), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels.shape[0])
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    print(f"scritto {path}")


src, prefix, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
tr = {}
for i in range(5):
    tr[i], rate = load(src / f"{prefix}_id{i}.wav")
n = min(t.shape[1] for t in tr.values())
en = tr[1][0][:n]
if len(sys.argv) > 4:
    voice, r2 = load(sys.argv[4])
    if r2 != rate:
        raise SystemExit(f"La voce nuova e' a {r2} Hz: va esportata a {rate} Hz.")
    voice = voice.mean(axis=0)
    if len(voice) > n:
        raise SystemExit(f"La voce nuova e' piu' lunga dell'originale ({len(voice)} > {n} campioni).")
    if len(voice) < n:
        print(f"voce nuova piu' corta di {(n - len(voice)) / rate:.3f} s: completata con silenzio")
        voice = np.concatenate([voice, np.zeros(n - len(voice))])
    tag = "voce_nuova"
else:
    voice = np.zeros(n)
    tag = "senza_voce"

X = np.vstack([tr[0][0], tr[0][1], en, tr[2][0], tr[3][0], tr[3][1]])[:, :n].T
a_out, b_out = [], []
for side in (0, 1):
    y = tr[4][side][:n]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    Xn = X.copy()
    Xn[:, 2] = voice
    a_out.append(Xn @ coef)
    g = np.dot(y, en) / np.dot(en, en)
    b_out.append(y - g * en + g * voice)
    print(f"canale {'LR'[side]}: g={g:.3f}  coeff. voce nel downmix={coef[2]:.3f}")

out.mkdir(parents=True, exist_ok=True)
save(out / f"{prefix}_id4_{tag}_A_ricostruito.wav", np.array(a_out), rate)
save(out / f"{prefix}_id4_{tag}_B_sottratto.wav", np.array(b_out), rate)
if tag == "voce_nuova":
    save(out / f"{prefix}_id1_voce_nuova.wav", voice, rate)
