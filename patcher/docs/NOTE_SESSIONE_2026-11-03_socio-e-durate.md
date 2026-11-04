# Nota di sessione — 3 novembre 2026: lo strumento del socio, "da tagliare", le durate esatte

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento. Segue `NOTE_SESSIONE_2026-11-02_avanzamento.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "Dove siamo
> (al 4 novembre 2026)".

## In breve

- **Strumento del socio, versioni 16 e 17** (idee dal gruppo dei revisori):
  - un solo pulsante grande, **OK, BUONA**, al posto di "ok" e "segnala";
  - una nota scritta dal controllo segnala da sola la battuta, e cancellando le note la
    segnalazione si toglie;
  - il segnalibro, uno per personaggio e per nome;
  - un promemoria in cima al report;
  - le misure salvate a parte.
- **"Da tagliare":** la postazione non toglie più il silenzio alle battute lunghe solo per
  quello. Lo fa chi registra, che le riconsegna. Lo dicono, in giallo, il copione dei
  doppiatori, lo strumento del socio e il foglio dell'avanzamento.
- **Le durate:** tutti i controlli confrontano i campioni con l'originale. Il controllo
  all'arrivo delle consegne non concede più 50 ms, e sotto il centesimo i messaggi danno
  millisecondi e campioni.
- **Postazione:** ricevute le consegne arrivate dal ponte il 31 ottobre e il 1° novembre.
  `patch_data` ha 1.445 battute. Niente tagliato, per decisione dell'utente.
- **Pubblicati:** lo strumento del socio (versione 17), le pagine dei 76 pacchetti e
  `Ponte.gs` (dall'utente, con `impostaAvanzamento()`). Il controllo dopo: 76 pacchetti
  uguali.

## 1. Lo strumento del socio

- **OK, BUONA:** è l'unico pulsante dell'esito.
- **La nota segnala da sola:** `segnala_da_nota`, chiamata dopo ogni nota salvata dal
  report, che manda anche lo zip della consegna.
  - Se la battuta ha almeno una nota per tipo con un testo, l'esito per la registrazione di
    oggi diventa "segnalazione", anche se prima era un ok.
  - Se le note non ci sono più, la segnalazione si toglie.
  - OK, BUONA la sovrascrive.
  - Una nota vuota, una pagina vecchia senza zip o uno zip di un altro personaggio non
    cambiano l'esito.
- **Il segnalibro:**
  - `dati/segnalibri.json`, uno per personaggio e per nome scritto in "Il tuo nome", solo
    su quella copia dello strumento;
  - "🔖 segna qui" sotto OK, BUONA;
  - sotto le note, "Riparti dalla riga N" con "Vai alla riga N";
  - nella pagina principale, la colonna "il tuo segnalibro".
- **Il promemoria rosso** in cima al report: resta davanti anche scorrendo la pagina.
- **Le misure a parte** (`dati/voci`, con `VERSIONE_MISURE`):
  - un report si rifà da lì quando cambia solo la pagina (`VERSIONE`), con la stessa
    chiave: md5 dello zip, originali presenti, md5 di durate e filmati;
  - la prima volta con la versione 16 lo strumento rimisura comunque tutto, perché la
    cache nasce misurando.
- **"Da tagliare":** le categorie di taglio sono gialle, non più verdi. Il riassunto
  elenca le righe, c'è il filtro "tutte le da tagliare", e il giallo compare anche
  nell'avanzamento.
- Prove con consegne finte:
  - 29 sul report (cache, nota che segnala e toglie, segnalibro, richieste sbagliate);
  - 16 contro un finto ponte;
  - più l'avanzamento, e la pagina guardata nel browser.

## 2. "Da tagliare" al posto di "lo facciamo noi"

- **Copione dei doppiatori** (`make_packet.py`):
  - la pastiglia dice "da tagliare · 2.57s contro 2.56s";
  - sotto la battuta, quanto silenzio togliere e "consegnala di nuovo: così com'è non entra
    nel gioco";
  - l'avviso alla consegna elenca le righe.
- **Un difetto vecchio corretto:** sotto i 10 ms di coda il messaggio non diceva quanto
  togliere ("Togli di silenzio"). Ora lo dice anche in millisecondi, per esempio "7 ms in
  coda". Lo stesso vale nello strumento del socio (`secondi`).
- **Guide:** doppiatori, socio e pannello. Il pannello tiene `taglia`, ma con l'avviso che
  per ora non si usa.
- **Foglio dell'avanzamento:** la misura "da tagliare" in giallo scuro sullo sfondo della
  riga. Le regole di `Ponte.gs` usano formule senza funzioni, che valgono in ogni lingua del
  foglio. Provato col finto Google Fogli.

## 3. Le durate

- **Il sospetto:** molte battute lasciate fuori da `componi` risultavano "0.00 s" più
  lunghe dell'originale. Controllate tutte le 112:
  - Wwise non aggiunge campioni: il `.wem` ha gli stessi campioni del wav;
  - l'inglese dei pacchetti è identico all'originale del gioco, campione per campione;
  - nessuna battuta è pari all'originale. 4 sono più lunghe di meno di 1 ms, 6 di meno di
    10 ms, e tutte e 10 sono da tagliare.
- **Cosa è cambiato:**
  - `misure.piu_lunga`: sotto il centesimo, "dura 0.31 ms (15 campioni) più dell'originale";
  - `verifica_consegne` confronta i campioni con l'originale del pacchetto. Senza
    l'originale usa la durata del copione con mezzo millesimo di scarto
    (`misure.TOLLERANZA`, prima 0,05 s);
  - ora l'arrivo delle consegne e `componi` dicono le stesse 112 battute troppo lunghe. Le
    altre 6 dell'arrivo stanno nei soundbank.

## 4. Altro

- `verifica`: la frase "le battute col prefetch tacciono" compare solo quando le nostre
  battute sono installate e il soundbank no. Prima usciva anche col gioco tutto originale.
- Upstream controllato: niente dopo la 0.9.7, `upstream/main` è fermo al 27 settembre.
- `RIPARTIRE_DA_QUI.md` riscritto: la §2 è il quadro di oggi con l'elenco delle note, e i
  lavori aperti sono ripuliti.

## 5. Cosa resta

- Nei lavori aperti della §7 di `RIPARTIRE_DA_QUI.md`. In particolare:
  - dire ai doppiatori delle battute da tagliare;
  - dire al socio che il primo controllo rimisura;
  - condividere il foglio.
- Sotto il millesimo di differenza il copione dei doppiatori può mostrare due durate
  uguali in una battuta da tagliare. L'utente ha chiesto di lasciarlo così per ora.
