# Componenti di terze parti

I pacchetti Windows e Linux includono wheel originali, senza modifiche, ottenuti
da PyPI e verificati tramite SHA-256 durante il build e durante l'installazione:

- CustomTkinter 5.2.2 — licenza CC0-1.0;
- darkdetect 0.8.0 — licenza BSD-3-Clause;
- packaging 26.3 — licenze Apache-2.0 o BSD-2-Clause;
- PyCryptodome 3.23.0 — licenze BSD-2-Clause e dominio pubblico.

I testi di licenza completi restano all'interno dei rispettivi wheel. Le
origini e gli hash accettati sono in `patcher/requirements-win64.lock`,
`patcher/requirements-linux-x86_64.lock` e nei builder di release. Il wheel di
PyCryptodome è specifico di ogni piattaforma; gli altri componenti mantengono
le stesse versioni bloccate.

Su Windows, il bootstrap opzionale può installare Python 3.13.15 x64 ufficiale,
distribuito dalla Python Software Foundation sotto la PSF License Agreement.
L'installer non è incluso nello ZIP di ERITA: viene ottenuto tramite WinGet o,
quando WinGet è assente, direttamente da `python.org` dopo la convalida di
dimensione, SHA-256, firma Authenticode ed editore.

Il pacchetto Linux include il runtime portatile
`cpython-3.13.15+20260924-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz`
del progetto Astral `python-build-standalone`. Contiene CPython 3.13.15 ed è
distribuito secondo i termini applicabili di Python e dei componenti inclusi
nel runtime. Il file accettato ha 34.993.852 byte e SHA-256
`d0b640eed27fbdd6f5f2bd33444aee53df2c8863f8b2a96f4094717411e3de9c`.

Il runtime e i wheel Linux sono inclusi nel `tar.gz` ufficiale di ERITA. Nessuno
dei due viene scaricato al primo avvio e nessuna dipendenza viene installata
nel sistema operativo.
