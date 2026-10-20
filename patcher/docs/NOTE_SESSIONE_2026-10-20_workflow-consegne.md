# Nota di sessione — 20 ottobre 2026 (pomeriggio): il giro delle consegne

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la procedura stabile sta in
> `doppiaggio/docs/WORKFLOW_CONSEGNE.md`. Segue la nota della mattina,
> `NOTE_SESSIONE_2026-10-20_filmati-bink.md`.
> **Committato in locale, non pushato**: nel repo `doppiaggio` `8c9737c`, `ab5c7da`,
> `167cc6b`. Nel repo ERITA solo questa nota; il codice del patcher non è cambiato.

## In breve

Dalla domanda "come provo i WAV italiani con ERITA?" è nato un giro completo e ripetibile,
tutto da `doppiaggio/lavora.cmd`, dallo zip della consegna su Drive al gioco. È stato provato
sulla **prima consegna vera, Gostoc** (Riccardo Roversi, 101 battute su 140): ricevuta,
controllata, codificata, installata con ERITA e **verificata byte per byte negli archivi del
gioco**. Manca l'ascolto in gioco.

Le fasi successive (versioni di test per altri tester, prima release) sono descritte in un
documento temporaneo, con le proposte di automazione:
[ERITA — Dalle voci alla prima versione italiana](https://claude.ai/code/artifact/564f9f82-5bc9-4cd4-b6fe-cb60fd6772c2).

---

## 1. Il giro, in comandi

Tutti da `doppiaggio/lavora.cmd` (cioè `python tools/lavora.py`), con il Python di Windows.

| comando | cosa fa |
|---|---|
| `prepara` | una volta per postazione: percorsi in `postazione.json`, vgmstream r2117 scaricato e verificato, estrazione degli originali inglesi in `audio_en/` |
| `nuove [cartella]` (doppio clic) | cerca i `CONSEGNA_*.zip` nella cartella delle consegne, anche dentro gli zip-cartella di Drive, e lavora solo i nuovi |
| `tutto <zip…>` | lo stesso giro su zip precisi (trascinati su `lavora.cmd`) |
| `ricevi`, `controlla`, `codifica`, `componi` | i quattro passi del giro, uno alla volta |
| `report [personaggio]` | report generale e report di ogni consegna |
| `stato` | avanzamento per personaggio |
| `prova` | controlla gioco e `patch_data`, apre ERITA dal checkout con il bypass |
| `verifica` | dopo "Installa doppiaggio": legge le battute dagli archivi del gioco e le confronta byte per byte |

## 2. Cosa c'è di nuovo in `doppiaggio/tools/`

- **`postazione.py`**: percorsi del gioco, di ERITA e di Wwise in `postazione.json` (fuori da
  git), trovati dalle librerie Steam e da `C:\Audiokinetic`. Riconosce dallo SHA-256 se
  `sd.bdt`/`sd_dlc02.bdt` sono vanilla 1.17.1, o di ERITA o di ERPT-BR (dal `patched_sha256`
  nei manifest dei backup in `%LOCALAPPDATA%`), con una cache degli hash.
- **`lavora.py`**: il punto d'ingresso. Il registro degli zip ricevuti
  (`manifest/zip_ricevuti.csv`) li riconosce dallo SHA-256. Salta i già ricevuti e quelli più
  vecchi dell'ultima consegna dello stesso personaggio (`--ancora` per forzare), e riceve in
  ordine di data. `componi` rifà `ERITA/patch_data/` da zero con ogni battuta pronta e la
  convalida con `patcher.patch_data.validate_patch_directory`, con il bypass, prima di
  sostituire la vecchia.
- **`report_consegne.py`**: `report/index.html` con le battute da rifare o da ascoltare, e
  `report/consegna_<zip>.html` con **tutte** le battute di una consegna. Per ogni battuta:
  - stato, durata contro l'originale, silenzi, rumore di fondo, byte contro lo slot, qualità
    e kbps contro l'inglese;
  - tre lettori audio: ITA, GIOCO (il `.wem` decodificato) ed EN;
  - una spunta "ascoltata", che resta nel `localStorage` del browser.

  Dopo ogni giro si apre una finestra per consegna nuova (oltre 5, il report generale).
- **`encode_wem.py`**:
  - gira su Windows, senza WSL;
  - rifiuta di codificare senza l'originale in `audio_en/`: prima codificava in mono 48 kHz
    senza avvisare;
  - non cancella più da `encoding.csv` gli esiti degli altri personaggi;
  - **il ripiego per chi sfora lo slot scende fino a qualità 0** (prima si fermava a 4), e le
    battute entrate sotto qualità 4 vengono elencate "da ascoltare".
- **`extract_wem.py`**: legge l'indice dal `.bhd` del gioco e i byte da un `.bdt` vanilla
  verificato, cioè il gioco se è originale, altrimenti il backup del patcher. La chiave RSA
  ora la cerca in `patcher/engine.py`.
- **`verifica_consegne.py`**: scrive i percorsi sempre con `/`. Da Windows produceva `\`, e
  tutte le 10.064 righe di `consegne.csv` risultavano cambiate.

## 3. Decisioni prese

- **Le registrazioni non vanno in git.** Sarebbero gigabyte: la copia di riferimento è lo
  zip di ogni consegna su Drive (**Consegne**), che **non si cancella**. Restano locali, e
  ignorati, anche `audio-ita*/` e i fogli dello stato delle consegne (`zip_ricevuti.csv`,
  `consegne.csv`, `encoding.csv`, `patch_data.csv`). Il registro in git, su un'altra
  postazione, farebbe saltare zip mai ricevuti lì. Un commit con i WAV di Gostoc, solo
  locale, è stato tolto con un reset.
- **Ripiego fino a qualità 0.** Il limite resta lo slot, cioè la dimensione del file inglese,
  quindi una battuta non pesa mai più dell'originale. Su Gostoc le 4 battute scese a qualità
  2-3 pesano 69-74 kbps, contro 62-73 kbps dei loro originali inglesi.
- **In `patch_data` va tutto il pronto, di tutti i personaggi.** Nel gioco si sente lo stato
  reale del doppiaggio.
- **Fuori da `patch_data`, sempre:** lo slot di Sellen `553755359`, e le 576 battute
  incorporate nei soundbank (`archivio` = `bnk_*`, quasi tutti versi). Per queste serve
  ricostruire il `.bnk`.

## 4. Gostoc, la prova vera

- `CONSEGNA_Gostoc_RiccardoRoversi_2026-10-18_0231.zip`: 101 WAV, 24 bit, mono, 48 kHz. Tutti
  nei tempi dell'originale.
- Codifica: 101 su 101 entrano. 4 solo a qualità 2-3 (righe 5, 67, 135 a 3; riga 123 a 2): da
  ascoltare.
- Gioco: PT-BR tolto dall'utente con `ERPT-BR.cmd` (archivi tornati vanilla alle 18:25),
  poi `lavora prova` e "Installa doppiaggio" in ERITA.
- `lavora verifica`:
  - **101 su 101 installate**: lo slot in `sd.bdt` è identico a `normalize_wem(nostro .wem)`
    e il resto dello slot è a zero;
  - tutte diverse dall'inglese e decodificabili da vgmstream con la durata giusta;
  - slot di Sellen originale;
  - 300 su 300 battute non doppiate (campione) identiche all'originale.

## 5. Stato della postazione a fine sessione

- **Sul gioco è installato ERITA con le 101 battute di Gostoc**, con il bypass di sviluppo.
  Prima di andare online: **Ripristina** in ERITA.
- `ERITA\patch_data\` contiene quelle 101 battute.
- `postazione.json` punta la cartella delle consegne a `C:\Users\leand\OneDrive\Documents\ERITA-ITA`.
- Il backup ERPT-BR in `%LOCALAPPDATA%\ERPT-BR\backups\` non serve più, perché `audio_en/` è
  già estratto.

## 6. Cose scoperte da sapere

- **`ERITA.cmd` dal checkout non parte**, perché richiede `wheelhouse/*.whl`. `prova` apre
  la GUI con `python -m patcher.patcher_gui`, con il Python di sistema (3.12, che ha
  `customtkinter` e `pycryptodome`). La GUI scrive avvisi ed errori in
  `doppiaggio/report/prova_erita.log`.
- **ERITA non installa sopra archivi già modificati**, e non vede i backup di ERPT-BR (cartelle
  diverse in `%LOCALAPPDATA%`). Un PT-BR installato va tolto con il suo patcher.
- **Con il bypass, se `patch_data/` accanto al checkout non è valida, il patcher passa ai
  candidati successivi** (cache, download del payload configurato, oggi il PT-BR). Per
  questo `componi` convalida prima di sostituire, e `prova` riconvalida prima di aprire ERITA.
- **Il patcher scrive il `.wem` come `normalize_wem`**: `fmt` e `data` del file, RIFF portato
  alla dimensione logica dello slot, il resto a zero. Così `verifica` sa cosa aspettarsi.
- **Durante una prova ho cancellato per sbaglio una battuta di Gostoc da `patch_data`.**
  `componi` l'ha ricreata identica. `verifica` ora segnala anche i file spariti da
  `patch_data` rispetto all'elenco di `componi`.

## 7. Lavori aperti

1. **Ascoltare Gostoc nel gioco** (cancello del Castello di Grantempesta): tempi, tagli,
   volume. Poi la spunta delle 101 battute nel report della consegna, a partire dalle 4 a
   qualità bassa.
2. **Automazioni proposte** (dettaglio e quadrante utilità/sforzo nel documento temporaneo):
   - Drive per desktop sincronizzato con la cartella delle consegne;
   - `prova --installa`: Ripristina, Installa e verifica senza GUI;
   - `versione-test`: payload fissato, pin su un branch, pacchetto costruito;
   - poi taglio dei silenzi a richiesta, pagina di correzioni per doppiatore, spunte condivise.
3. **Versioni di test** (fase E): decidere tester, contenuto, e se con o senza bypass.
4. **Release** (fase F), come nella §7 di `RIPARTIRE_DA_QUI.md`, più due voci:
   - decidere se il payload italiano ha bisogno dei soundbank ricostruiti;
   - adattare `rebuild_bnk_payload.py` per i 576 versi.
5. Gli strumenti di `doppiaggio/tools/` fuori dal giro (`extract_bnk.py`,
   `build_per_character.py`, `build_lacune.py`, `extract_talkparam.py`, `guida.py`) assumono
   ancora WSL e il gioco su `C:`.

## Per continuare

- Leggere `doppiaggio/docs/WORKFLOW_CONSEGNE.md` e il documento temporaneo.
- `cd doppiaggio && lavora.cmd stato` mostra a che punto sono le consegne.
- `lavora.cmd verifica` dice cosa c'è installato nel gioco in questo momento.
