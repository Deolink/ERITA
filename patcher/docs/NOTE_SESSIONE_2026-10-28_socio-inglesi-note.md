# Nota di sessione — 28 ottobre 2026: strumento del socio (inglesi da Drive, note), pagine troncate

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la procedura stabile sta in
> `doppiaggio/docs/WORKFLOW_CONSEGNE.md`, "Lo strumento di controllo del socio". Segue
> `NOTE_SESSIONE_2026-10-25_coda-dei-tagli.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al
> 28 ottobre 2026" (repo privato del doppiaggio: lì ci sono nomi ed elenchi per doppiatore).

## In breve

- Lo strumento del socio non vedeva gli originali inglesi di un personaggio arrivato dopo lo
  zip: gli inglesi stavano nello zip, e solo per i personaggi già ricevuti. Ora li scarica
  da solo dai pacchetti su Drive, e lo zip passa da 428 a 12 MB.
- Nel report del socio ci sono le note per i doppiatori: quelle che i doppiatori rimandano
  con le consegne, più quelle del socio. Dal report si prepara cosa ridare al doppiatore.
- Su questa postazione le risposte HTTP locali arrivavano troncate (un antivirus). Con
  HTTP/1.1 arrivano complete: corretti lo strumento del socio, il pannello e il server dei
  pacchetti.

## 1. Gli originali inglesi

Le consegne contengono solo `audio-ita/`, `lavorazione.json` e `pacchetto.json`: il pulsante
"Prepara la consegna" del pacchetto non ci mette gli inglesi, che il doppiatore ha già. Lo
strumento del socio li aveva solo dentro il suo zip.

Ora, a ogni controllo, per i personaggi con consegne scarica quelli che mancano o sono
cambiati (md5 di Drive) da `DialoguePacks/<personaggio>/audio/`, la cartella dei pacchetti
su Drive. L'account di servizio la vedeva già. Confrontati per md5 con quelli della
postazione: identici.

- **Velocità.** Uno alla volta erano circa 2,5 s a file (una connessione HTTPS ciascuno):
  40 minuti per un migliaio di file. Con 8 download insieme, 1.279 file in circa 7 minuti,
  misure comprese.
- La Drive API non scarica una cartella come zip (lo fa solo l'interfaccia web): si va file
  per file.
- Provato su una copia estratta dello zip, con il Python portatile: tutti i report con l'EN.
  Nel frattempo su Drive era arrivata una consegna nuova, presa con i suoi inglesi senza
  rifare lo zip.

## 2. Le note per i doppiatori

- Il pacchetto del doppiatore salva note, segnalazioni e spunte in `lavorazione.json`, e la
  consegna lo riporta indietro. Il report del socio mostra sotto ogni battuta la nota
  risultante, e l'avviso "adattamento segnalato".
- Il socio scrive nella stessa nota, con il suo nome. Le sue note stanno in
  `dati/note/<personaggio>.json`, nello stesso formato, e si uniscono con
  `server_pacchetto.unisci` (che ora viaggia nello zip del socio): se due persone cambiano la
  stessa nota restano le righe di tutte e due.
- Due uscite, in `per_i_doppiatori/`:
  - **solo le note**: un `lavorazione.json` da mettere nel pacchetto al posto del suo;
  - **pacchetto intero**: i file da `DialoguePacks`, gli originali, le registrazioni
    dell'ultima consegna e le note, con il `server.py` aggiornato.
- Provato su una consegna con 27 note e 27 segnalazioni: il `lavorazione.json` in uscita ha
  tutte le voci del doppiatore e cambia solo la nota scritta dal socio. Unito alla copia
  vecchia del doppiatore non perde niente. Il pacchetto rifatto, estratto e avviato, mostra
  la nota del socio.
- L'account di servizio legge soltanto: il file lo manda il socio. Per scrivere su Drive
  servirebbero il permesso di Editor, lo scope `drive` e file già esistenti (un account di
  servizio non ha spazio per crearne). `tools/drive_lavorazione_vuote.gs` (Google Apps
  Script) crea un `lavorazione.json` vuoto in ogni pacchetto, per quando servirà.

## 3. Le risposte troncate

- Lo script delle note non partiva: la pagina arrivava senza l'ultimo KB. Succedeva anche
  agli audio, sempre allo stesso byte, e anche con `python -m http.server`: non è il
  codice, è il traffico locale di python.exe filtrato da un antivirus.
- Con HTTP/1.0 il server chiude subito dopo la risposta, e la fine si perde. Con HTTP/1.1
  (`protocol_version`, connessione che resta aperta) le risposte arrivano complete, provato
  più volte di fila. Ogni risposta deve dichiarare la lunghezza: è stata aggiunta alla
  risposta 416 del server dei pacchetti, che non l'aveva.
- Corretti `tools/socio/controllo.py`, `tools/pannello.py` e `tools/server_pacchetto.py`.
  Provati: pagine e audio completi, richieste a intervallo, errori che non bloccano,
  salvataggi.
- I 75 pacchetti in `doppiaggio/pacchetti/` hanno il `server.py` nuovo. Quelli su Drive e
  quelli già in mano ai doppiatori no, finché non vengono aggiornati.

## 4. Altro

- `tools/impacchetta.py` metteva negli zip anche `audio-ita/` (registrazioni ricevute,
  tagliate) e `audio-ita-originali/`: ora `audio-ita/` entra vuota e gli originali dei tagli
  restano fuori. Rifatti e controllati i 76 zip.
- **Chiavi:** controllati i file e la storia git dei due repo, e Drive. Nessuna chiave privata,
  token o file di credenziali; l'indirizzo dell'account di servizio sta solo nel repo
  privato. Le copie della chiave sono tutte fuori da git (`distribuzione/` è esclusa).

## 5. La sera: i pacchetti su Drive

- **`lavora aggiorna-pacchetti <file> [personaggi] [--prova]`**: confronta per md5 i file
  indicati dei pacchetti locali con quelli in `DialoguePacks` e sostituisce solo quelli
  diversi, nello stesso file su Drive (stesso ID e proprietario, niente duplicati). Non
  tocca mai `lavorazione.json`.
- Scrive con un **secondo account di servizio**, Editor solo su `DialoguePacks`, con lo scope
  completo; la chiave sta solo sulla postazione (`lavora drive-pacchetti <chiave.json>`).
  Un account di servizio non ha spazio su Drive: modifica i file che ci sono, non ne crea.
- **Controllo dei pacchetti locali**: tutti completi e coerenti (ogni battuta del copione
  ha il suo audio inglese, `python/` identico ovunque). Le modifiche non committate a
  `index.html`, `copione.csv` e `0_LEGGIMI.html` erano solo fine riga.
- **Confronto con Drive**: 24 pacchetti completi ma con `0_LEGGIMI.html`, `copione.csv`,
  `index.html` e `server.py` vecchi, aggiornati in 93 file e ora identici alla postazione;
  **51 ancora della prima versione** (settembre: senza server, Python portatile, lanciatori,
  con gli audio chiamati in un altro modo), da sostituire a mano. Lo strumento del socio
  non rifà il "pacchetto intero" da quelli, e lo dice.
- Ricevuta la consegna nuova: `patch_data` a 1.160 battute; 14 tagli in sospeso.
- Nel report del socio la nota per il doppiatore sta in una riga sotto la battuta, larga
  quanto la tabella, come nel copione dei doppiatori.

## 6. Per continuare

1. Mandare al socio lo zip nuovo.
2. Sostituire su Drive i 51 pacchetti della prima versione.
3. Applicare i 14 tagli in sospeso.
4. Pulire le copie vecchie della chiave (dettaglio nella §7 di `RIPARTIRE_DA_QUI.md`).
