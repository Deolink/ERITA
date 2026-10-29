# Nota di sessione — 29 ottobre 2026: esito del controllo, durata in tre stati

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la procedura stabile sta in
> `doppiaggio/docs/WORKFLOW_CONSEGNE.md`, "Lo strumento di controllo del socio". Segue
> `NOTE_SESSIONE_2026-10-28_socio-inglesi-note.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al
> 29 ottobre 2026" (repo privato del doppiaggio: lì ci sono nomi ed elenchi per doppiatore).

## In breve

- Chi controlla le consegne segna ogni battuta come **ok** o **segnalazione**. L'esito arriva
  al doppiatore e il suo pacchetto lo mostra accanto a "consegnata".
- La pagina del pacchetto dice subito al doppiatore se una registrazione **entra**, **si
  sistema togliendo silenzio** o **va riregistrata**, con le stesse misure della postazione.
- Pagine rifatte nei pacchetti locali e caricate su Drive nei soli pacchetti completi.

## 1. L'esito del controllo

- **Nel report dello strumento portatile** la spunta "ascoltata", che restava nel browser,
  lascia il posto a due pulsanti, *ok* e *segnala*. Un secondo clic toglie l'esito. "Segnala"
  porta il cursore nella nota, dove si scrive il perché.
- **Un campo nuovo in `lavorazione.json`**:

  ```text
  "controllo": {"esito": "ok" | "segnalazione" | "", "consegna": "<zip ascoltato>",
                "chi": ..., "quando": ..., "storia": [...]}
  ```

  `server_pacchetto.CAMPI` lo valida e `unisci()` lo unisce come gli altri campi (vince il
  più recente). Lo strumento lo salva insieme alle note del socio, in
  `dati/note/<personaggio>.json`.
- **Vale per una registrazione, non per una battuta.** L'indice dello zip dà CRC e lunghezza
  di ogni file: se la registrazione della consegna ascoltata e quella di un'altra consegna
  coincidono, l'esito vale anche lì. Se il doppiatore la riconsegna diversa, il report
  mostra *da riverificare* e l'esito non esce nel `lavorazione.json` per il doppiatore
  (vale l'ultima consegna, quella che ha in `audio-ita/`).
- **Nel pacchetto** una seconda pastiglia accanto a *consegnata*: *verificata*,
  *segnalazione del controllo* o *non verificata*. Con una segnalazione la nota diventa
  arancione, con un'etichetta sua. Ci sono anche un contatore e un filtro.
- **Compatibilità:** il `server.py` dei pacchetti, quando salva, rilegge il file e cambia un
  campo solo: anche quelli vecchi conservano `controllo`. Le pagine vecchie lo ignorano, ma
  mostrano la nota.
- Provato su due consegne finte ricavate da una vera, con una battuta cambiata nella seconda:
  salvataggi, rifiuti (esito sconosciuto, zip di un altro personaggio, nome mancante),
  "da riverificare", uscita per il doppiatore, pagina del pacchetto, nota aggiunta dal
  doppiatore senza perdere l'esito.

## 2. La durata in tre stati

- Prima la pagina confrontava la durata totale con l'originale, con 50 ms di tolleranza:
  verde o rosso. Una battuta più lunga solo per il silenzio era rossa, mentre la postazione
  la sistema con `taglia`.
- Ora la pagina rifà in JavaScript `misure.misura` e `misure.rimedio`:
  - lettura del wav portato a 16 bit come `leggi_wav` (PCM 8/16/24/32, float 32/64), senza
    il decoder del browser, che ricampiona e cambierebbe le finestre;
  - finestre da 10 ms, testa sotto -45 dBFS, coda sotto -60 dBFS o fondo + 10 dB;
  - margini 50 ms in testa, 100 ms in coda, 0,01 s sotto l'originale.

  Verde se entra (senza tolleranza, come il report del socio), giallo se si sistema
  togliendo silenzio (con quanto, e l'invito a toglierlo nelle prossime), rosso se va
  riregistrata (con di quanto resta lunga). Anche il bordo della battuta e gli avvisi di
  "Prepara la consegna" seguono i tre stati.
- **Il wav intero si legge solo se i metadati dicono che è più lungo**: le altre bastano i
  metadati. Senza server (`file://`) il browser non lascia leggere il file: restano verde e
  rosso.
- **Confronto:** tutte le 1.261 registrazioni delle 8 consegne, misurate da `misure.py` e
  dalla pagina. Durata, testa, coda e fondo uguali entro 1e-9, categoria uguale per tutte.
  Le battute rosse di un personaggio coincidono con l'elenco "da riregistrare" della
  postazione.

## 3. Rifare le pagine dei pacchetti

- **`make_packet.py --solo-pagina`** rifà pagina, `server.py` e guida dei pacchetti senza
  ricopiare gli audio. Canali e frequenza li prende dal `copione.csv` del pacchetto.
- Il motivo: su questa postazione `--con-audio` cerca gli originali con il percorso della
  postazione di prima, e i `.wem` di `audio_en/` danno per 40 pacchetti un formato diverso
  da quello scritto nel copione, o nessuno. Con `--solo-pagina` nelle pagine non cambia
  nessuna riga di formato.
- **Su Drive** caricati `index.html`, `0_LEGGIMI.html` e `server.py` nei 24 pacchetti
  completi: 72 file, identici alla postazione. `aggiorna-pacchetti` va lanciato sempre con
  i nomi dei pacchetti completi: senza nomi prende anche quelli della prima versione, a cui
  le pagine nuove non vanno date (punterebbero ad audio che lì hanno un altro nome).

## 4. La sera

- **Una sottocartella di Consegne si ignora.** Su Drive, in Consegne, c'è una cartella di
  revisione dei pacchetti, con dentro zip che si chiamano come le consegne ma non lo sono.
  `drive.CARTELLE_IGNORATE` la elenca e `drive.ignorata()` la riconosce (minuscole, senza
  spazi ai lati). La saltano `lavora scarica`, `lavora nuove` (anche dentro gli
  zip-cartella che Drive fa scaricando una cartella intera) e lo strumento portatile, su
  Drive e in locale. `scarica` dice quanti file ha ignorato.
- **Controllo di tutti i pacchetti su Drive**, sui file in cima, i lanciatori e
  `python/python.exe`:
  - i 24 completi sono identici alla postazione, tranne `copione.csv` in quattro: quello
    locale contiene le note arrivate con le consegne;
  - i pacchetti della prima versione non hanno server, guida, lanciatori e Python, e hanno
    gli originali con i nomi vecchi (`<id>.wav`). In due l'utente li aveva già sostituiti a
    mano: identici.
- **Cestinare i file vecchi sui pacchetti della prima versione** non si può fare con
  l'account di servizio: è Editor, non proprietario, e su un Drive personale toglierebbe i
  file solo dalla cartella, lasciandoli orfani nello spazio del proprietario.
  - Lo fa `tools/drive_pulisci_prima_versione.gs`, un Google Apps Script lanciato dal
    proprietario. In ogni pacchetto senza `server.py` sposta nel cestino `audio/` (solo se
    ha soltanto nomi vecchi), `index.html` e `copione.csv`; lascia `audio-ita/`.
  - Ha una prova che non tocca niente. Provato prima su un Drive finto (oggetti al posto di
    `DriveApp`), con i casi: vecchio, già nuovo, nomi misti, completo, filmato.
  - **La prova vera ha trovato un errore:** il pacchetto del filmato non ha `server.py` ma
    ha un `copione.csv`, e sarebbe finito tra quelli da pulire. Il conteggio non tornava
    (50 invece di 49). Corretto: si saltano i pacchetti con `filmato.json` e le cartelle
    senza `index.html` né `audio/`.
  - Lanciato su 49 pacchetti: 3.629 audio vecchi nel cestino. Ricontrollato con l'account
    in sola lettura: nei 49 resta solo `audio-ita/`, il filmato è intatto.
- **Si carica dalla postazione:** i pacchetti in `pacchetti/<personaggio>/` sono già quelli
  nuovi. Confrontati con una copia pulita, sono identici file per file; in più c'è solo
  `audio-ita/` vuota, che non va trascinata, perché Drive non unisce le cartelle con lo
  stesso nome, ne fa una seconda.
- **Pulizia:** fatto solo un rapporto (copie di costruzione dello strumento con la chiave,
  zip vecchi, prove, zip dei pacchetti con le pagine di prima). Niente cancellato.
- In PowerShell 5.1 un messaggio di commit con le virgolette, passato con `-m`, si spezza in
  più argomenti: meglio `git commit -F <file>`. E `Set-Content -Encoding utf8` ci aggiunge un
  BOM in testa.

## 5. Per continuare

1. Caricare i 49 pacchetti svuotati su Drive, poi ricontrollare file per file.
2. Decidere della consegna nuova su Drive, fuori dalla cartella di revisione, che ha
   "ADATTAMENTO" nel nome.
3. Mandare al socio lo zip del 29 ottobre al posto di quello del 28.
4. Rifare la foto del report nella guida del socio.
5. La pulizia, dopo conferma.
6. Gli altri lavori aperti nella §7 di `RIPARTIRE_DA_QUI.md`.
