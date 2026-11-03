# Nota di sessione — 2 e 3 novembre 2026: il foglio dell'avanzamento

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: il piano, con le scelte e le prove, sta in
> `doppiaggio/docs/PIANO_AVANZAMENTO.md`. Segue `NOTE_SESSIONE_2026-11-02_consegna-unica.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al
> 2 novembre 2026, notte".

## In breve

- **La richiesta:** un quadro di come vanno i lavori, battuta per battuta: cosa manca, cosa è
  da controllare, cosa ha avuto l'ok. Deve aggiornarsi da solo e poterlo vedere anche altre
  persone.
- **La soluzione:** lo strumento del socio calcola lo stato di ogni battuta e lo mostra in una
  scheda sua. Lo manda anche al ponte, che riscrive un foglio Google, "ERITA - avanzamento",
  nella radice su Drive accanto al registro. Il foglio si condivide in sola lettura con la
  condivisione di Google.
- **Pubblicati:**
  - `Ponte.gs` (dall'utente, poi `impostaAvanzamento()`); la prova di sicurezza passa,
    compresi i casi nuovi;
  - lo strumento del socio (versione 15).
- **Il foglio ha i dati veri** dalla notte del 2 novembre: 12 personaggi con consegne, 2.088
  battute, 79 ok, 10 segnalate, 1.489 da controllare, 510 mancanti.

## 1. Gli stati

| stato | vuol dire | tocca a |
|---|---|---|
| manca | nel copione, non nella consegna unica del personaggio | doppiatore |
| da controllare | consegnata, senza un esito valido per la registrazione di oggi | controllo |
| segnalata | il controllo l'ha segnalata e la registrazione non è cambiata | doppiatore |
| ok | il controllo ha dato l'ok a questa registrazione | nessuno |

Le regole erano già nello strumento:
- un esito vale solo se la registrazione ascoltata e quella di oggi sono lo stesso file
  (`esito_valido`, tolto da `da_controllare`);
- il totale di un personaggio sono le sue righe di `dati/durate.csv`.

Accanto allo stato c'è la misura (a posto, si taglia, da riregistrare), salvata per battuta
nel riepilogo; per questo la versione 15 rimisura una volta tutto.

## 2. Cosa è cambiato

- **Strumento del socio** (`tools/socio/controllo.py`):
  - `avanzamento()`, `copione()`, `conta_note()`, `doppiatore_di()`;
  - `GET /__avanzamento__` e la scheda "Avanzamento" nella pagina, con le righe colorate per
    stato;
  - con il ponte, `scrivi_foglio()` alla fine di ogni controllo e `foglio_da_aggiornare()`
    60 secondi dopo l'ultimo esito, presa o nota. Il segno `dati/avanzamento_da_scrivere`
    fa riprovare all'avvio.
- **Ponte** (`Ponte.gs`):
  - `avanzamento_scrivi`, per socio e postazione. Con `prova: true` controlla i dati e torna
    le righe senza scrivere;
  - `impostaAvanzamento()` dall'editor: crea il foglio la prima volta, poi ne rifà solo la
    forma.
- **Sicurezza del foglio:**
  - colonne e "tocca a" li decide il ponte;
  - un testo che comincia con `= + - @` o con un apostrofo prende un apostrofo davanti e
    resta testo, così il nome scritto da un doppiatore non diventa una formula (per esempio
    una `IMPORTDATA` verso fuori);
  - i numeri devono essere numeri; ci sono limiti di righe e di lunghezza; un lock evita due
    scritture insieme.
- **Aspetto:**
  - le righe in più si inseriscono prima dell'ultima, così le regole di colore si allungano;
  - il filtro si rifà con i criteri di prima;
  - il colore dello stato va su tutta la riga, con formule senza funzioni (`=$E2="ok"`) che
    valgono in ogni lingua del foglio;
  - personaggio, numero e note sono più grandi e in grassetto;
  - la barra del riepilogo è un testo colorato.
- **Il nome del doppiatore:** quello dell'invio più recente che non sia una revisione. Gli
  zip delle revisioni hanno nel nome REVISIONE o ADATTAMENTO al posto della persona.
- `tools/ponte.py prova-sicurezza`: cinque casi nuovi, tutti con `prova: true`, e la verifica
  che una formula torni testo.
- Guide: `tools/ponte/LEGGIMI.md` ("Il foglio dell'avanzamento") e la guida del socio.

## 3. Prove

- Strumento del socio con consegne finte, 13 prove: stati, misura, note, personaggio senza
  consegne, ok che torna da controllare quando la battuta è rifatta.
- Contro un finto ponte, 16 prove: scrittura, rifiuto col segno che resta, sei modifiche
  che fanno una scrittura sola, fine del controllo, esito dalla pagina, Host sbagliato.
- `Ponte.gs` nel browser con un finto Google Fogli: 39 prove.
- Sul ponte vero:
  - la prova di sicurezza;
  - una scrittura di prova della postazione, guardata dall'utente: formule rimaste testo,
    barra, colori e filtri giusti;
  - poi i dati veri, con una copia dello strumento col codice del socio. La scorta è stata
    riempita prima con i file della postazione, così dal ponte sono arrivati solo i file
    nuovi.

## 4. Cosa resta

- Pubblicare lo strumento del socio con il nome giusto per le revisioni e la guida nuova
  (`lavora pubblica --socio`).
- L'utente condivide il foglio. Prima va controllato che la radice e le cartelle sopra non
  siano condivise con altri: chi vede la cartella vede anche il foglio e il registro.
- Possibili più avanti: un attivatore orario del ponte che segna "nuovo invio da
  controllare" anche a strumento spento; la scrittura anche dalla postazione; un cruscotto
  sopra il foglio.
