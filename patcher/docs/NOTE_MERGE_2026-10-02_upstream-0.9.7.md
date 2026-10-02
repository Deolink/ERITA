# Nota di sessione — 2 ottobre 2026: merge dell'upstream 0.9.6/0.9.7 (con Linux)

> Appunto di lavoro per riferimento futuro. Riassume il merge da
> `upstream/main` (repo `lorepamplona/ERPT-BR`, tag `v0.9.7`) nel fork
> `Deolink/ERITA`, sul branch `merge/upstream-0.9.7` (merge `14c3299`). Note
> precedenti: [0.9.3](NOTE_MERGE_2026-09-16_upstream-0.9.3.md),
> [0.9.5](NOTE_MERGE_2026-09-25_upstream-0.9.5.md).

## Cosa ha fatto l'upstream

- **0.9.6, manifesto Steam facoltativo.** La compatibilità si decide dai file
  audio reali: profilo 1.17.1, con SHA-256 dei BHD, dimensioni dei BDT e, prima
  di scrivere, SHA-256 completo dei BDT. `appmanifest_1245620.acf` diventa solo
  informativo: un manifesto mancante, diverso o copiato non blocca e non
  autorizza nulla. Nuovo errore `GameFilesCompatibilityError`
  (`ERITA-FILES-001`).
- **0.9.7, Linux e Steam Deck.**
  - `ERITA.sh` (ex `ERPT-BR.sh`) richiama `interno/INICIAR_LINUX.sh`.
  - Lo script autentica il runtime portatile Astral CPython 3.13.15
    (`runtime/…tar.gz`, 34.993.852 byte) e i wheel Linux, poi li installa
    offline nel profilo. Su Linux i backup stanno in
    `$XDG_STATE_HOME/ERITA/backups`, la cache in `$XDG_CACHE_HOME/ERITA/payload`,
    runtime e dipendenze in `$XDG_DATA_HOME/ERITA`.
  - Rilevamento di Steam nativo, Flatpak e Snap, e dei processi tramite `/proc`.
  - Nuovi `tools/build_linux_release.py` e `tools/verify_linux_release.py`.
- **0.9.7, mitigazione per Sellen.** L'effetto non verbale `553755359.wem`
  durava più dell'originale durante l'animazione della Pietra Brillante
  Primordiale e bloccava la missione. Ora i tool lo escludono dal payload (resta
  vanilla) e i verificatori rifiutano un pacchetto che lo contenga. Il payload
  PT-BR passa a 9.240 file.

## Decisioni

- Supporto Linux incluso.
- La parte Linux si verifica con la **CI del fork su una PR**, perché in locale
  (Windows) si possono provare bene solo i test e `bash -n` in WSL.
- Restano valide le decisioni del 25/09:
  - installazione attiva;
  - `rebuild_bnk_payload.py` e `build_candidate_payload.py` restano in
    portoghese, con solo i percorsi ERITA;
  - le variabili interne `ERPT_*`/`ERPTBR_*` non cambiano, anche nei `.sh`.
- I tool di release Linux sono tradotti come quelli Windows.

## Cosa ho fatto

1. Punto di partenza: `main` a `97afc88`, 260 test verdi.
2. **Merge:** 20 file in conflitto, più i file Linux nuovi.
   - Per codice e test ho preso la versione upstream e poi ho ritradotto tutte
     le stringhe entrate con il merge.
   - Controllo: l'AST di `engine.py`, `patcher_gui.py`, `build_source_release.py`,
     `bnk.py` e dei due tool PT-BR, ignorando le stringhe, è identico
     all'upstream.
   - `patch_data.py` e `verify_source_release.py` differiscono solo per il
     bypass di sviluppo e il suo blocco.
3. **Linux**
   - `git mv ERPT-BR.sh ERITA.sh`, con modo `100755` verificato.
   - Messaggi dei due `.sh` in italiano e titoli `kdialog`/`zenity` "ERITA".
   - `app_data="$data_base/ERITA"`.
   - Marcatori `.erita-runtime-sha256` e `.erita-deps-identity`.
   - Controllato che i testi non contengano le parole vietate di
     `FORBIDDEN_LAUNCHER_PATTERNS` (`source `, `eval `, `curl`, `https://`…).
4. **Bypass anche su Linux.** Nell'upstream `verify_linux_release.py` controlla
   solo i `.sh`, non i `.py`. Ho aggiunto `FORBIDDEN_SOURCE_PATTERNS` con
   `erita_dev_unsafe_skip_payload_pin` e `_verify_source_patterns`, più il test
   `test_verifier_blocks_dev_payload_pin_bypass`. Il test che costruisce e
   verifica un pacchetto usando i sorgenti reali svuota quel dizionario con
   `mock.patch.dict` (c'è un commento che lo spiega). Altrimenti fallirebbe
   proprio perché il bypass è ancora nel codice.
5. **Strumenti nuovi della sessione** (in scratchpad, non nel repo): sostituzione
   di testo solo dentro i letterali stringa, tramite `tokenize`, con controllo
   di compilazione e chiavi tutte usate. È stato utile per i ~200 messaggi dei
   tool Linux.
6. **Documenti.**
   - README, SECURITY, MIGRACAO, INCIDENTE e THIRD_PARTY_NOTICES aggiornati alla
     0.9.7, con installazione Linux, manifesto facoltativo e runtime Astral.
   - Nuove `docs/RELEASE-0.9.6.md` e `docs/RELEASE-0.9.7.md`, con la nota per
     ERITA. `DETAILS_URL` punta a `docs/RELEASE-0.9.7.md`.
   - Il modulo di segnalazione ora chiede piattaforma, sistema, tipo di Steam e
     filesystem.

## Verifica eseguita

- `python -m unittest discover -s tests` → **320 test, OK** (5 skip su
  Windows).
- `compileall` pulito.
- `bash -n` sui due script in WSL Ubuntu: OK.
- Ricerche finali di pulizia:
  - nessun codice `ERPT-*`;
  - nessun percorso `ERPT-BR`;
  - `ERPT-BR` solo nei crediti, negli URL `lorepamplona`, nei due tool PT-BR e
    nelle note che citano l'upstream;
  - nessuna parola portoghese nei testi per l'utente.
- La CI Linux va confermata sulla PR.

## Cosa NON ho fatto

- Nessuna prova reale di `ERITA.sh` (servirebbero il runtime Astral e i wheel
  Linux in un pacchetto completo) né della GUI.
- Pin `PAYLOAD_*` ancora PT-BR v0.9.7. Bypass di sviluppo ancora presente. Nessun
  tag pubblicato: il trigger di release del fork è il tag `v0.9.7`, presente in
  locale perché arriva dall'upstream.

## Da ricordare per il doppiaggio italiano

**Caso Sellen.** Un audio più lungo dell'originale non va solo fuori sincrono:
può **bloccare una missione**. Il limite di durata chiesto agli attori
(`doppiaggio/STATO.md`) è quindi un vincolo rigido, da controllare anche sui
versi e sugli effetti non verbali. `553755359.wem` deve restare vanilla anche
nel payload italiano: i verificatori di release lo impongono già.
