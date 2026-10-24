# Nota di sessione — 24 ottobre 2026: Drive, taglio del silenzio, prova da zero, pannello e strumento del socio

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la procedura stabile sta in
> `doppiaggio/docs/WORKFLOW_CONSEGNE.md`, sezioni "Una volta per postazione: collegare
> Drive" e "Quando arrivano consegne". Segue `NOTE_SESSIONE_2026-10-20_workflow-consegne.md`.

## In breve

Prima il giro delle consegne partiva dagli zip già scaricati a mano da Drive. Adesso il
doppio clic su `doppiaggio/lavora.cmd` comincia leggendo la cartella **Consegne** di Drive,
scarica solo gli zip nuovi o aggiornati e poi prosegue con il giro di sempre (`nuove`):
ricevi, controlla, codifica, componi, report.

**Collegato e provato dal vero il 24 ottobre.** L'indirizzo dell'account di servizio e il
progetto Google sono scritti solo nei documenti privati (`doppiaggio/docs/RIPARTIRE_DA_QUI.md`, repo privato del doppiaggio, "Questa
postazione"). La chiave è in `%APPDATA%\ERITA\drive-chiave.json`. La copia in Download è stata cancellata, dopo aver
verificato che fosse identica. Il primo doppio clic ha portato 5 consegne vere, fino ai
report.

## 1. La scelta: account di servizio

Le strade messe a confronto:

| strada | contro principale |
|---|---|
| Google Drive per desktop | Sincronizza nei due sensi: un file cancellato o spostato per sbaglio nella cartella locale sparisce anche da Drive, e gli zip su Drive sono la copia di riferimento. Inoltre al doppio clic uno zip appena caricato può non essere ancora sincronizzato. |
| Drive API con OAuth dell'utente | Lettura su tutto il Drive dell'utente. Con l'app in modalità "Test", Google fa scadere il token ogni 7 giorni. |
| **Drive API con account di servizio** (scelta) | Una chiave JSON da custodire. |
| rclone, link pubblico | Un binario in più, oppure le registrazioni rese pubbliche. |

L'account di servizio vede **solo** Consegne, condivisa come Visualizzatore. Lo scope è
`drive.readonly`, quindi non può cambiare niente. Non scade, non apre il browser, e si
revoca cancellando la chiave su Google Cloud. Non servono librerie nuove: urllib per la
Drive API v3, e `pycryptodome` (già richiesto) per firmare il JWT RS256.

## 2. Cosa è cambiato in `doppiaggio/`

- **`tools/drive.py`** (nuovo): token dall'account di servizio, elenco ricorsivo della
  cartella con `md5Checksum`, `size`, `createdTime` e `modifiedTime`, ricerca della
  cartella "Consegne" tra quelle condivise. Il download passa da un file temporaneo
  nascosto, controlla dimensione e md5 contro Drive e solo allora rinomina; la data del
  file è quella di Drive. `python tools/drive.py` mostra cosa vede l'account.
- **`tools/lavora.py`**:
  - `drive <chiave.json> [link]`: copia la chiave in `%APPDATA%\ERITA\drive-chiave.json`
    (fuori dal repo), trova Consegne, scrive `drive` in `postazione.json` e mostra cosa
    vede, senza scaricare;
  - `scarica [--elenco]`: confronta Drive con il registro e con gli zip locali, e stampa i
    gruppi nuovi, aggiornati, già scaricati ma non ricevuti, già ricevuti, altri file.
    Scarica nuovi e aggiornati nella cartella delle consegne, con le sottocartelle di
    Drive;
  - `nuove` (il doppio clic) chiama `scarica` per primo quando `drive` è configurato. Se
    Drive non risponde lo dice e prosegue con gli zip locali. Ordine di data e zip più
    vecchi saltati restano regole di `nuove`;
  - il registro `manifest/zip_ricevuti.csv` ha la colonna **`md5`** accanto a `sha256`.
    Le righe vecchie la prendono da sole quando lo zip è ancora in locale;
  - `NOME_CONSEGNA` accetta il suffisso ` (…)` dei doppioni, e lo stesso vale per
    `ricevi_consegna.py`;
  - `prepara` dice se Drive è collegato e se la chiave c'è.
- **`tools/postazione.py`**: `impronte()` calcola SHA-256 e, se richiesto, MD5 in una
  lettura sola, nella stessa cache di `postazione.json`.
- **`lavora.cmd`**, **`docs/WORKFLOW_CONSEGNE.md`**, **`docs/RIPARTIRE_DA_QUI.md`**:
  aggiornati.

## 3. Le regole di "nuovo" e "aggiornato"

- Il confronto è sull'**md5 del contenuto**, quello che Drive dà come `md5Checksum`. Si
  confronta con gli md5 del registro e con quelli degli zip già nella cartella locale (e in
  `arrivi/`). Così niente di ricevuto o già scaricato si riscarica, anche se rinominato o
  spostato.
- **Aggiornato** vuol dire: md5 mai visto, ma il posto locale di quel file esiste già, o
  il nome è quello di una consegna già ricevuta. Succede quando uno zip viene ricaricato su
  Drive con "Sostituisci". La copia locale di prima non si cancella: diventa
  `….zip.precedente-<data>`, che `nuove` ignora.
- **Ogni file di Drive ha sempre lo stesso posto locale.** Se in una cartella di Drive due
  file hanno lo stesso nome, il più vecchio per `createdTime` tiene il nome e gli altri
  prendono ` (<inizio dell'ID>)`. La prima versione dava il nome a chi arrivava prima nel
  giro: la prova l'ha colta, perché i due file si scavalcavano a ogni giro.

## 4. Prove

Contro un **finto server della Drive API** in locale, con registro, `postazione.json`,
`arrivi/` e cartella delle consegne temporanei e una chiave RSA generata per la prova:

1. niente di nuovo: Gostoc già ricevuto, e la sua riga del registro prende l'md5;
2. uno zip nuovo: scaricato nella sua sottocartella, md5 controllato, data di Drive;
   rilanciato, non si riscarica;
3. lo stesso zip ricaricato con contenuto diverso: "aggiornato", la copia di prima diventa
   `.precedente-…` e arriva quello nuovo;
4. un download che non torna con l'md5 di Drive: nessun file lasciato, né definitivo né
   temporaneo;
5. due file con lo stesso nome nella stessa cartella: tutti e due scaricati, con nomi
   stabili, e al giro dopo nessuno dei due si riscarica;
6. cartella non condivisa: il messaggio dice con quale indirizzo condividerla;
7. `nuove` completo: scarica, poi `ricevi` salta gli zip finti (nessun personaggio) e
   Gostoc (già ricevuto).

Lo script della prova non è nel repo.

**Dal vero, su Drive** (senza file finti, come chiesto dall'utente):

- `lavora.cmd drive "…\Downloadchiave.json"`: chiave copiata, cartella **CONSEGNE**
  trovata da sola. Su 6 zip, Gostoc risultava già ricevuto e 5 erano **nuovi**: consegne
  vere mai scaricate.
- Primo giro di `nuove`, con l'OK dell'utente: 5 zip scaricati (circa 500 MB, md5
  controllato), ricevuti, controllati, codificati. `patch_data` ricomposta: **760 battute
  pronte** di 6 personaggi. Aperti i 5 report.
  - Da rifare: 205 battute, quasi tutte troppo lunghe, più 4 che sforano lo slot. Da
    ascoltare: 16.
  - Uno zip contiene un `desktop.ini`, finito in `audio-ita/` e segnalato come nome
    sbagliato.
- Secondo giro: "6 già ricevuti, niente di nuovo su Drive" e "Nessuna consegna nuova".
  Ogni riga del registro ha l'md5.

Nota: su Drive quasi tutti gli zip stanno nella radice di CONSEGNE, non nelle
sottocartelle per personaggio, tranne uno. `lavora` li scarica come stanno.

## 5. Report: tagliare o riregistrare

Delle 203 battute troppo lunghe, quasi tutte lo erano solo per il silenzio, spesso più di
un secondo in fondo. Il report ora dà a ogni troppo lunga una seconda etichetta, calcolata da
`misure.rimedio()`:
- **si taglia la coda**: 148;
- **si tagliano testa e coda**: 37;
- **da riregistrare**: 18, di cui una sta in un soundbank. L'elenco per personaggio è nei
  report e in `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, repo privato del doppiaggio.

Le regole del calcolo:
- prima si toglie la coda, poi la testa;
- restano sempre 50 ms di silenzio per lato;
- il risultato deve venire **10 ms sotto** l'originale, perché `componi` non ammette nemmeno
  un campione in più.

Ogni etichetta ha il suo filtro, e in testa alla pagina un riquadro le conta. In
`da_rifare.csv` ci sono le colonne `rimedio`, `taglio_testa_s` e `taglio_coda_s`.

## 6. `lavora taglia` e `manifest/tagli.csv`

- `tools/tagli.py` taglia senza perdite: toglie fotogrammi interi e lascia gli altri chunk
  (`bext`, `junk`). È provato byte per byte su un WAV a 24 bit di una consegna.
- L'originale va in `audio-ita-originali/`.
- Il registro `manifest/tagli.csv` è **in git**. Contiene personaggio, file, SHA-256
  dell'originale, campioni tolti e SHA-256 del risultato. Dopo ogni `ricevi` i tagli si
  riapplicano da soli, e `ricevi` riconosce come "già presente" la versione tagliata di un
  file.
- **Dal vero:** 184 battute tagliate (148 coda, 36 testa e coda). `patch_data` è passata
  **da 760 a 938**.
  - Una battuta è stata saltata dal controllo di sicurezza: il taglio sarebbe arrivato a
    meno di 30 ms dalla voce. Il report la segna ancora "si taglia": va ascoltata e decisa
    a mano.
  - Alcune battute tagliate stanno in un soundbank: non possono ancora entrare in
    `patch_data`.
- **`--annulla`** provato su una battuta: l'originale torna identico, poi il nuovo taglio
  dà gli stessi byte di prima.
- **Due difetti trovati dalle prove e corretti:**
  - Due battute di una consegna avevano **la stessa registrazione**. Il registro,
    riconoscendo l'originale solo dal contenuto, applicava il taglio dell'una anche
    all'altra. Ora un taglio vale solo per personaggio, file e contenuto insieme.
  - Nel ciclo che stampa i tagli riapplicati avevo riusato la variabile `nome`, e il
    registro aveva preso come nome di una consegna quello di un WAV. Il registro e
    il report sbagliato sono stati sistemati, e ora il confronto di `da-zero` controlla
    anche i nomi.

## 7. `lavora da-zero`

Mette da parte lo stato in `prove-da-zero/<data>/prima/` (con ritorno indietro se uno
spostamento non riesce), riscarica tutto da Drive in una cartella a parte, rifà il giro e
confronta. `--ripristina` rimette lo stato di prima.

- Prova su un personaggio solo: identico.
- Prova completa, su 6 consegne: **identico**:
  - 978 registrazioni, 184 originali dei tagli, 958 `.wem`: anche la codifica di Wwise è
    deterministica;
  - 938 battute in `patch_data` con gli stessi esiti;
  - le stesse 6 consegne.
- `--ripristina` provato.
- Il primo tentativo completo si era fermato a metà, perché una pagina di `report/` era
  aperta nel browser. Lo stato è stato rimesso a mano, senza perdite. Ora `report/` non si
  sposta più, e gli spostamenti si annullano da soli se uno fallisce.
- In `doppiaggio/prove-da-zero/` restano le cartelle delle prove (circa 2 GB): si possono
  cancellare.

## 8. Il pannello (`tools/pannello.py`)

- Il doppio clic su `lavora.cmd` apre una pagina nel browser con un pulsante per ogni
  comando, divisi in Consegne, Battute troppo lunghe, Nel gioco, Manutenzione e Il socio.
- Mostra la tabella dei personaggi, l'uscita del comando in corso e i link ai report, che
  il pannello serve lui stesso insieme all'audio dei pacchetti.
- Solo `127.0.0.1`; controlla l'Host; per lanciare un comando serve il token della pagina;
  i comandi sono una lista fissa.
- `lavora.cmd <comando>` da terminale funziona come prima.
- Guida: `doppiaggio/docs/GUIDA_PANNELLO.pdf`.

## 9. Lo strumento del socio (`tools/socio/`, `tools/impacchetta_socio.py`)

- `lavora.cmd socio` (o il pannello) crea `distribuzione/ERITA-Controllo_<data>.zip`, circa
  430 MB. Contiene:
  - il programma;
  - `misure.py` e `drive.py`, gli stessi della postazione;
  - le durate di tutte le battute;
  - gli originali inglesi dei 6 personaggi consegnati;
  - la chiave;
  - il Python 3.12.10 embeddable **completo** (SHA-256 fissato, firma PSF *Valid*);
  - la guida.
- Il socio fa doppio clic, poi preme **Controlla le consegne**: scarica da Drive solo il
  nuovo e scrive un report per consegna, con rimedio, ITA ed EN e la spunta.
- `drive.py` ora firma il JWT anche **in Python puro** se manca `pycryptodome`: è provato
  identico alla libreria, e ottiene un token vero.
- `tools/misure.py` è il modulo unico delle misure. Lo usano il report, la codifica
  (`leggi_wav`) e lo strumento del socio.
- Guida: `doppiaggio/docs/GUIDA_CONTROLLO_SOCIO.pdf`.
- **Provato dal vero** con il suo Python portatile, dalla cartella costruita: 6 consegne
  scaricate e misurate. I numeri tornano con quelli della postazione.
  - In più segnala 11 versi che stanno **in un soundbank** e sforano di 6-49 ms. La postazione non li segnala perché sono sotto la
    tolleranza di 50 ms e non vengono codificati. Il report del socio li marca "dentro un
    soundbank".
  - Ho anche estratto lo zip in una cartella nuova: la pagina si apre e Drive risponde.
- **Sicurezza dei due server, corretta.** Un percorso come `/report/../chiave/…` usciva
  dalla cartella dei report: sullo strumento del socio avrebbe servito la chiave. Ora il
  percorso si normalizza prima del controllo, e nessuno dei due usa più il server di file
  generico. Provato con curl: le varianti con `..` e `%2e%2e` danno 404.

## 10. Per continuare

1. **Nel gioco ci sono ancora solo le 101 battute di Gostoc**, mentre `patch_data` ne ha
   938. Per sentire le nuove: pannello, Apri ERITA, Ripristina, Installa, Verifica.
2. Ascoltare le battute tagliate in testa (36), segnate "da ascoltare" nei report.
3. Far riregistrare le battute segnate "da riregistrare" e chiarire le due battute con la
   stessa registrazione: chi, quali righe e cosa dire sono in `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, repo privato del doppiaggio (§7).
4. Mandare al socio lo zip e la guida, senza passare da Drive: lo zip contiene la chiave.
5. Piccola cosa: `ricevi_consegna.py` potrebbe ignorare `desktop.ini` e simili dentro gli
   zip.
