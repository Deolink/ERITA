# Nota di sessione — 30 ottobre 2026, sera: le note per tipo

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: il progetto e le scelte stanno in
> `doppiaggio/docs/PIANO_NOTE_PER_TIPO.md`, il formato nell'intestazione di
> `doppiaggio/tools/server_pacchetto.py`. Segue `NOTE_SESSIONE_2026-10-30_ponte-in-uso.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`.

## In breve

- **Le note sono per tipo, e più d'una per battuta.** Sotto ogni battuta ci sono sette
  pulsanti colorati (Adattamento, Tempi, Pause, Silenzi, Direzione, Dizione, Altro): ognuno
  aggiunge una riga di quel tipo, su cui si scrive. Il cestino la cancella. Al massimo 30
  note per battuta.
- **Una nota Adattamento segnala da sola la battuta** come problema di adattamento, e
  cancellare l'ultima toglie la segnalazione, se era stata una nota ad accenderla. Il
  pulsante "segnala" resta, per segnalare senza scrivere.
- **Stesso pannello nel copione dei doppiatori e nel report del socio.** Tempi e Silenzi
  propongono già il testo dalle misure ("circa il 13% in meno", "0.12s in coda").
- **Pubblicato:** 75 pacchetti e lo strumento del socio sul ponte. La verifica dopo
  (`pubblica --prova`) dà 0 da aggiornare, 75 uguali.

## 1. Le scelte

- Decise dall'utente: tipo **Altro** (anche per le note di prima e per le domande),
  **chiunque** può cancellare, **Pause e Silenzi separati**, **massimo 30** note, la nota
  Adattamento **accende il segnalino**.
- Fatte in sessione: ogni nota è un campo suo della battuta (`nota_<id>`), così unione,
  storia e pulizia restano quelle di prima. Una nota cancellata resta come "cancellata",
  altrimenti un'unione con una copia vecchia la farebbe tornare. La nota unica di prima
  (`nota`) non si converte: si vede come Altro.
- Il pannello (`NOTE_CSS`, `NOTE_JS`) sta in `server_pacchetto.py`, l'unico file che arriva
  sia ai pacchetti sia allo strumento del socio. Lo strumento del socio è alla versione 11:
  i report si rifanno.

## 2. Provato

- Su copie di Nepheli (103 note vecchie) e del socio con la consegna di prova di Gostoc,
  nello scratchpad, senza ponte: aggiungere, salvare, firma, segnalino acceso e spento,
  cancellare, filtro per tipo, nota vuota che sparisce, ricarica dal server.
- Uno script di prova delle unioni (cancellata contro copia vecchia, conflitti, limite,
  pulizia), fuori dal repo.
- **Non provato a video:** il copione aperto con doppio clic, in sola lettura (il browser
  integrato non esegue script sui file locali).

## 3. Commit

- `doppiaggio/` `8de6b2c` (piano) e `66ce1b7` (strumenti, guide, schermata nuova del
  report in `docs/img/socio_report.png`). Non pushati.
- Le pagine di `pacchetti/`, rifatte per la pubblicazione, restano non committate come
  quelle di prima.

## 4. Da fare, o da decidere

- Le note vecchie che cominciano col tipo ("TEMPI: …", "Adattamento: …") si potrebbero
  mostrare col tipo giusto invece che come Altro. Non fatto: da decidere.
- Il socio deve solo riavviare lo strumento: si aggiorna da solo.
