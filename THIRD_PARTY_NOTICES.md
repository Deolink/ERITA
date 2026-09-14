# Componenti di terze parti

Il pacchetto Windows include wheel originali, senza modifiche, ottenuti da PyPI e
verificati tramite SHA-256 durante il build e durante l'installazione:

- CustomTkinter 5.2.2 — licenza CC0-1.0;
- darkdetect 0.8.0 — licenza BSD-3-Clause;
- packaging 26.3 — licenze Apache-2.0 o BSD-2-Clause;
- PyCryptodome 3.23.0 — licenze BSD-2-Clause e dominio pubblico.

I testi di licenza completi restano all'interno dei rispettivi wheel. Le
origini e gli hash accettati sono in `patcher/requirements-win64.lock` e
`tools/build_source_release.py`.

Il bootstrap opzionale può installare Python 3.13.15 x64 ufficiale, distribuito
dalla Python Software Foundation sotto la PSF License Agreement. L'installer non è
incluso nello ZIP di ERPT-BR: viene ottenuto tramite WinGet o, quando WinGet è
assente, direttamente da `python.org` dopo la convalida di dimensione, SHA-256,
firma Authenticode ed editore.
