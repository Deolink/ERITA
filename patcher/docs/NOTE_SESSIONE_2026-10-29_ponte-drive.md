# Nota di sessione — 29 ottobre 2026, a tarda sera: il ponte su Drive

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: piano, regole di sicurezza e misure stanno in
> `doppiaggio/docs/PIANO_AGGIORNAMENTI_DRIVE.md`, i passi per pubblicare il ponte in
> `doppiaggio/tools/ponte/LEGGIMI.md`. Segue `NOTE_SESSIONE_2026-10-29_controllo-e-durate.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al
> 29 ottobre 2026, a tarda sera" (repo privato del doppiaggio).

## In breve

- **L'obiettivo:** pacchetti dei doppiatori e strumento del socio si aggiornano da soli da
  Drive e ci mandano da soli le loro modifiche, **senza dare in giro chiavi di account di
  servizio**.
- **La strada scelta:** un ponte Apps Script nell'account Google del progetto. Chi chiama
  manda un codice personale e revocabile, e il ponte fa solo quello che il ruolo di quel
  codice permette.
- **È in prova** in una cartella separata del Drive del progetto, con una copia di un
  pacchetto: funziona sul ponte vero. Niente è ancora in uso con i doppiatori.

## 1. Perché un ponte e non altro

- **Le alternative valutate:**
  - accesso Google per persona (OAuth): avviso "app non verificata", token che scadono in
    prova, e il Python dei pacchetti non ha `ssl`;
  - Apps Script "come utente": dalla pagina locale non passano i cookie Google;
  - Drive per desktop: scartato prima;
  - un server proprio: da tenere acceso e proteggere;
  - link pubblici con chiave API: solo lettura.
- **Il ponte gira come il proprietario.** Quindi:
  - i file creati sono suoi (un account di servizio non ne crea);
  - nessuno fa accessi Google;
  - i permessi stanno nel codice dello script.
- **Su Drive oggi** la cartella delle consegne è "chiunque abbia il link può modificare",
  e i doppiatori caricano col proprio account. Col ponte quel link si potrà chiudere.

## 2. Come funziona

- **Ruoli:** doppiatore (un personaggio), socio, postazione.
  - I codici stanno nelle proprietà dello script come impronta SHA-256.
  - Il ponte costruisce i percorsi da nomi controllati con espressioni strette, e non
    accetta ID di Drive dall'esterno.
  - Non cancella mai niente: un file riscritto diventa una versione nuova.
  - Ogni richiesta, rifiuti compresi, va in un foglio di registro.
- **La consegna** non è più uno zip.
  - Il pacchetto carica in `audio-ita/` della sua cartella su Drive le registrazioni nuove o
    cambiate (per md5), e per ultimo scrive `consegne/CONSEGNA_….json` con nome e md5 di
    ogni file.
  - Postazione e socio rifanno da quell'elenco lo zip di prima (`ponte_client`), con sempre
    gli stessi byte: `ricevi_consegna`, i report e l'esito del controllo restano com'erano.
- **Le note vanno da sole nei due sensi:**
  - il doppiatore le manda a ogni salvataggio;
  - il socio 20 secondi dopo l'ultima modifica, e se non arrivano restano in sospeso fino al
    prossimo avvio;
  - il copione aperto guarda le note del controllo ogni 2 minuti, il report del socio quelle
    del doppiatore ogni minuto.
- **Aggiornamenti automatici:**
  - pagina, server e copione del pacchetto, e il programma del socio, si sostituiscono solo
    se l'elenco `versione.json` è firmato con la chiave della postazione (Ed25519 in Python
    puro, `tools/firma.py`, provata con i vettori della RFC 8032), non è più vecchio
    dell'ultimo applicato ed è per quel pacchetto;
  - i file sostituiti vanno in `_vecchi/`;
  - se cambia il server, esce con codice 3 e il lanciatore lo riavvia.
- **Pulsanti:** il doppiatore ne ha due (apri, invia la consegna), il socio tre (apri,
  controlla, pubblica; pubblica ora è solo "manda tutto adesso").
- **Senza `ponte.json`** pacchetti e strumento funzionano come prima. Provato: lo zip di
  consegna non contiene il codice, e il codice non si legge dal server del pacchetto.

## 3. Cosa si è imparato

- **Antivirus della postazione:** con `urllib`, che chiede al server di chiudere dopo ogni
  risposta, una risposta locale su tre si perdeva, come i troncamenti del 28. `ponte_client`
  usa connessioni persistenti (`http.client`), che risparmiano anche la stretta di mano TLS.
- **Il messaggio "app non verificata"** lo vede solo il proprietario quando autorizza lo
  script, non chi usa il ponte.
- **Velocità:**
  - all'inizio circa 3 s a file: una chiamata per file, la cartella riletta a ogni
    scrittura, le scritture in fila;
  - con i lotti (`carica_molti`, `scarica_molti`), la ricerca per nome, la cache delle
    proprietà e la lettura e scrittura in parallelo (`UrlFetchApp.fetchAll`, permesso
    `script.external_request`): scaricare 0,8 s a file;
  - caricare 2,7 s a file, ma qui il limite è la linea (circa 2,4 Mbit/s in uscita, più il
    33% del base64).
- **Quote di Apps Script per un account gratuito:**
  - 6 minuti a chiamata, 30 esecuzioni contemporanee, 50.000 letture di proprietà al
    giorno, 20.000 richieste UrlFetch al giorno;
  - il limite vero è lo spazio: 15 GB per l'account.
- **Un finto ponte locale** (stesse operazioni, su una cartella) è servito a provare
  pagina, socio e postazione prima di toccare Google.

## 4. Cosa resta

- Le decisioni aperte del piano (§8): codice per pacchetto o per persona, pacchetti di
  gruppo, consegne di adattamento e di revisione.
- Riscrivere le §5-§7 del piano con la consegna in `audio-ita/`.
- Facoltativo: caricare in binario direttamente su Drive, con una sessione di caricamento
  aperta dal ponte, senza base64 (da verificare il CORS dal browser).
- **Il passaggio vero:**
  - radice vera al posto di quella di prova;
  - i 75 pacchetti ripubblicati con `ponte.py pubblica --tutto`;
  - un'ultima distribuzione a mano dei pacchetti e dello strumento del socio, senza chiave;
  - poi chiudere il link pubblico delle consegne e cancellare le chiavi degli account di
    servizio.
