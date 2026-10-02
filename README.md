# ERITA — Elden Ring Doppiaggio ITA (WORK IN PROGRESS)

Patcher per applicare il doppiaggio in Italiano a Elden Ring (PC).

Fork di [ERPT-BR](https://github.com/lorepamplona/ERPT-BR) di [@lorepamplona](https://github.com/lorepamplona), adattato per il doppiaggio italiano da [@Deolink](https://github.com/Deolink).

> [!IMPORTANT]
> Il codice di ERITA è allineato alla versione **0.9.7** del progetto
> originale, che installa il doppiaggio su Elden Ring **1.17.1** (Steam BuildID
> `25080141`). I banchi audio vengono ricostruiti sui banchi originali di
> quella versione, per preservare i suoni aggiunti dal gioco, inclusi i clic
> dell'interfaccia che sparivano con le versioni 0.9.1 e 0.9.2. La 0.9.7
> applica anche una mitigazione prudente al bug segnalato nella missione di
> Sellen (un effetto non verbale dell'animazione della Pietra Brillante
> Primordiale resta originale), mantiene la regola della 0.9.6 che rende
> facoltativo l'`appmanifest` di Steam e aggiunge un primo pacchetto portatile
> per Linux x86_64 e Steam Deck in modalità desktop.
>
> **Il pacchetto audio italiano non è ancora pronto**: le registrazioni sono in
> corso, quindi ERITA non ha ancora una release installabile.

## Download

**Download:** (WORK IN PROGRESS)

Quando sarà pubblicata una release, dalla pagina
[Releases](https://github.com/Deolink/ERITA/releases) andrà scaricato il
pacchetto del proprio sistema:

- Windows x64: `ERITA-v0.9.7-Windows.zip`;
- Linux x86_64/Steam Deck: `ERITA-v0.9.7-Linux-x86_64.tar.gz`.

Sono entrambi pacchetti completi per l'utente: installer in codice sorgente,
dipendenze verificate e payload audio. Non scaricare gli archivi automatici
**Source code** di GitHub e non provare a eseguire separatamente i file interni
del payload.

## Installazione su Windows

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Estrai **tutto** il contenuto di `ERITA-v0.9.7-Windows.zip` in una cartella
   nuova e vuota. Non estrarre sopra una versione precedente.
3. Fai doppio clic su `ERITA.cmd`.
4. Conferma la cartella `ELDEN RING\Game` rilevata tramite Steam oppure
   selezionala.
5. Clicca su **Installa doppiaggio** e attendi la conferma finale.
6. Apri il gioco normalmente tramite Steam. Poiché un `appmanifest` potrebbe
   essere stato copiato, non viene mai usato per promettere che l'online sia
   disponibile: prima di giocare online conferma che Steam riconosca e
   aggiorni questa installazione.

L'utente vede un solo punto di ingresso: `ERITA.cmd`. Al primo utilizzo
verifica il pacchetto e prepara un ambiente isolato. Se necessario, installa il
CPython 3.13.15 x64 ufficiale nel profilo dell'utente. Negli utilizzi
successivi, lo stesso file apre l'interfaccia senza rifare un'installazione
valida.

Non eseguire il patcher come amministratore. Se Windows nega la scrittura,
chiudi il gioco e l'EAC e usa una libreria Steam scrivibile dal tuo account,
oppure modifica solo il permesso della cartella del gioco.

## Installazione su Linux e Steam Deck

Il supporto della 0.9.7 è iniziale e pensato per **Linux x86_64**. Su Steam
Deck usa la **modalità desktop**.

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Estrai tutto il contenuto di `ERITA-v0.9.7-Linux-x86_64.tar.gz` in una
   cartella nuova e vuota su un'unità Linux `ext4`. Non estrarre sopra una
   versione precedente.
3. Avvia `ERITA.sh` dal gestore file oppure, da un terminale aperto nella
   cartella estratta, con `./ERITA.sh`.
4. Conferma la cartella `ELDEN RING/Game` rilevata oppure selezionala.
5. Clicca su **Installa doppiaggio** e attendi la conferma finale.
6. Apri il gioco normalmente dalla stessa installazione di Steam.

Il rilevamento cerca le installazioni di Steam native, Flatpak e Snap e segue
anche le librerie registrate in `libraryfolders.vdf`. Il pacchetto include il
runtime portatile Astral `python-build-standalone` 20260924 con CPython 3.13.15
e tutte le dipendenze bloccate: al primo avvio non servono il Python di
sistema, `sudo` né la rete. **Non eseguirlo come root.**

Questa prima versione Linux deve ancora completare la convalida in CI e i test
su hardware reale prima di qualunque promessa sul funzionamento online. Il
filesystem supportato all'inizio è `ext4`; NTFS, exFAT e btrfs non sono ancora
garantiti senza test specifici.

## Modalità online

Il payload su cui si basa la 0.9.7 è stato testato su Windows dal progetto
originale ERPT-BR, con il **suo** pacchetto audio PT-BR, in una sessione reale
sulla 0.9.4: gioco avviato normalmente da Steam, Easy Anti-Cheat e connessione
online attivi. Il test si è concluso con successo e i suoni dei clic hanno
continuato a funzionare. La 0.9.7 differisce solo perché lascia originale
l'effetto non verbale dell'animazione di Sellen; questa mitigazione deve ancora
essere confermata giocando la missione. ERITA usa lo stesso metodo, ma non ha
ancora un pacchetto audio proprio da provare online. Il patcher non disattiva
né modifica l'EAC, non inietta librerie e non cambia il modo di avviare il
gioco. Il test precedente non vale automaticamente per Linux/Proton: lì
l'online resta senza garanzie finché non ci sarà un test fisico riproducibile.

Il metodo diretto modifica dati dentro i BDT, ma non riscrive né rifirma gli
indici BHD. Le risorse modificate non corrispondono più agli hash salted
originali. L'installer accetta solo le divergenze esatte del piano e del
payload autenticati; qualunque differenza in più viene rifiutata. Una sessione
online riuscita non elimina questo limite tecnico.

Quel risultato vale per la versione e la sessione testate: non è una garanzia
di rischio zero né di compatibilità con futuri aggiornamenti del gioco,
dell'EAC o delle regole del servizio. Se Steam aggiorna Elden Ring, ripristina
o verifica i file e attendi una versione che riconosca il nuovo profilo reale
dei file.

Riconoscere il profilo locale dei file senza un manifesto valido conferma la
compatibilità dell'audio, ma non che l'installazione sia registrata in Steam né
che l'online sia disponibile in quell'ambiente. L'assenza del manifesto, da
sola, **non blocca l'installazione del doppiaggio**.

## Cosa è cambiato nella 0.9.7

- nuovo pacchetto portatile per Linux x86_64 e Steam Deck in modalità desktop;
- rilevamento di Steam nativo, Flatpak e Snap, comprese le librerie aggiuntive
  registrate in `libraryfolders.vdf`;
- runtime Astral `python-build-standalone` 20260924 con CPython 3.13.15
  fissato;
- dipendenze Linux incluse e installate localmente in modalità offline;
- nessun bisogno di Python di sistema, `sudo` o rete al primo avvio;
- stesse convalide del profilo reale 1.17.1;
- mitigazione prudente del bug segnalato nella missione di Sellen: l'effetto
  non verbale `553755359.wem` resta originale, senza togliere nessuna battuta
  doppiata.

## Cosa è cambiato nella 0.9.6

- `appmanifest_1245620.acf` non è più obbligatorio per installare;
- un manifesto assente, illeggibile, divergente o copiato non blocca un profilo
  reale di file riconosciuto;
- un manifesto copiato non autorizza mai file incompatibili;
- l'interfaccia spiega quando Steam e l'online non possono essere confermati;
- i BHD, le dimensioni dei BDT e il baseline completo restano autenticati prima
  di ogni scrittura;
- il payload audio è esattamente lo stesso pacchetto corretto della 0.9.5.

## Cosa è cambiato nella 0.9.5

- l'audio ora si trova direttamente nella cartella `patch_data` del pacchetto
  estratto;
- non c'è più uno ZIP audio grande dentro lo ZIP da scaricare;
- l'interfaccia e il metodo di installazione restano gli stessi;
- il pacchetto resta un unico download con un unico punto di ingresso;
- il contenuto audio viene convalidato con lo stesso inventario e lo stesso
  SHA-256 canonico dell'albero prima di qualunque scrittura nel gioco.

## Correzione audio mantenuta dalla 0.9.4

- banchi Wwise ricostruiti usando la struttura originale di Elden Ring 1.17.1;
- media ed eventi nuovi del gioco preservati durante l'inserimento delle
  battute;
- clic del menu e altri suoni originali assenti nel vecchio pacchetto
  ripristinati;
- installazione, reinstallazione idempotente e ripristino verificati;
- convalida del gioco ripetuta subito prima di qualunque scrittura;
- installazione con un clic senza un eseguibile proprio del progetto.

Per riferimento, il payload PT-BR autenticato dell'upstream contiene 9.240
file: 8.968 WEM e 272 alias BNK, corrispondenti a 136 banchi fisici
ricostruiti. Il payload italiano avrà numeri e hash propri.

## Chi ha usato la 0.9.1 o la 0.9.2

Quelle versioni sostituivano banchi attuali con banchi vecchi e potevano
rimuovere i clic del menu e i suoni delle cutscene. La versione 0.8.4 usa lo
stesso vecchio payload e non è un'alternativa sicura.

Prima di installare di nuovo:

1. Apri il pacchetto attuale e usa **Correggi audio (ripristina)** se esiste un
   backup transazionale valido.
2. Se il ripristino non è disponibile o fallisce, usa **Steam > Elden Ring >
   Proprietà > File installati > Verifica integrità dei file**.
3. Conferma l'audio originale e solo dopo installa la nuova versione.

Consulta anche la [migrazione dal vecchio eseguibile](MIGRACAO.md) e il
[rapporto sull'incidente](docs/INCIDENTE-0.9.1.md).

## Diagnostica di compatibilità e blocchi

La compatibilità si decide dai file audio installati, non dall'`appmanifest`
di Steam. Nel controllo rapido il patcher verifica l'insieme e lo SHA-256 degli
indici BHD e le dimensioni dei BDT. Prima di qualunque scrittura autentica anche
lo SHA-256 completo dei BDT originali o di un backup già autenticato.

L'`appmanifest_1245620.acf` è solo un'informazione ausiliaria. Se manca, è
illeggibile o indica un altro BuildID, ma il profilo reale dei file viene
riconosciuto, l'installazione resta consentita e l'interfaccia segnala che
Steam e l'online non sono stati confermati. Così funziona anche per chi ha già
messo un manifesto esterno nella libreria.

Non serve scaricare, copiare né distribuire quel manifesto. Non aggiorna nessun
file di Elden Ring e non autorizza mai da solo un'installazione. Una versione
vecchia può essere supportata davvero solo con un'analisi strutturale sicura o
con un profilo e un payload propri: fingere il BuildID della 1.17.1 non cambia
i suoi file.

I file incompatibili usano il codice `ERITA-FILES-001` e interrompono
l'operazione prima di modificare il gioco, con una spiegazione che si può
copiare nella diagnostica.

Il pulsante **Diagnostica** genera localmente un report JSON con versione del
patcher, BuildID indicato, fase, tempo, avanzamento, sistema e log recenti. La
generazione del report non avvia una nuova lettura dei file del gioco e non
include hash dei singoli file, contenuto del manifesto, salvataggi, nome utente,
percorso completo o SteamID. Rivedi comunque il contenuto prima di pubblicarlo.

Niente viene inviato automaticamente. Il pulsante **Apri segnalazione** si
limita a copiare la diagnostica e ad aprire il
[modulo di compatibilità](https://github.com/Deolink/ERITA/issues/new?template=compatibilidade.yml);
l'invio resta manuale e la issue sarà pubblica.

## Backup, ripristino e aggiornamenti

Su Windows il backup si trova in `%LOCALAPPDATA%\ERITA\backups`. Su Linux si
trova in `$XDG_STATE_HOME/ERITA/backups` se la variabile è definita, altrimenti
in `~/.local/state/ERITA/backups`. È collegato all'installazione scelta e al
profilo reale dei file audio. Il patcher autentica i BHD, le dimensioni dei BDT
e lo SHA-256 completo dei BDT originali, prepara copie temporanee, registra un
journal transazionale e rilegge il risultato prima di annunciare il successo.
Un backup fuori da quel profilo non viene mai ripristinato sul gioco attuale.

Ripristina l'audio originale prima di spostare o rinominare la libreria Steam.
Usa lo stesso account del sistema per installare e ripristinare. Se il gioco si
aggiorna, esegui la verifica di integrità di Steam e attendi una versione di
ERITA che riconosca il nuovo profilo reale dei file.

I file di una transazione interrotta (anche le copie `.erita-stage-*` e
`.erita-restore-*`) vengono preservati per la diagnostica; il programma non
cancella mai ricorsivamente un percorso che potrebbe essere stato sostituito da
un link o da una junction.

## Limiti attuali

- Windows x64;
- supporto iniziale a Linux x86_64 e Steam Deck in modalità desktop, con Steam
  nativo, Flatpak o Snap;
- `ext4` è il filesystem Linux supportato all'inizio; NTFS, exFAT e btrfs
  richiedono ancora una convalida specifica;
- Elden Ring 1.17.1, con BuildID Steam ausiliario corrispondente `25080141`;
- audio WEM/BNK; il vecchio pacchetto opzionale di cutscene `.bk2` resta
  rifiutato perché non ha un manifesto crittografico pubblico;
- le versioni future del gioco richiedono una convalida e una release
  specifiche.

## Sviluppo e test

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

Il pacchetto Linux usa `patcher/requirements-linux-x86_64.lock` e il runtime
portatile fissato; il pacchetto di release viene testato separatamente in CI
prima della pubblicazione.

Per avviare `ERITA.cmd` (o `ERITA.sh` dentro un pacchetto Linux completo)
direttamente dal checkout serve una cartella `patch_data` accanto allo script:
vuota basta per aprire l'interfaccia e usare il ripristino. Per provare file
`.wem`/`.bnk` italiani non ancora fissati nel manifesto del payload, mettili in
`patch_data` e imposta la variabile di sviluppo
`ERITA_DEV_UNSAFE_SKIP_PAYLOAD_PIN=1`. Finché quella variabile resta nel codice,
`tools/verify_source_release.py` e `tools/verify_linux_release.py` rifiutano
qualunque release.

La CI rifiuta il launcher dinamico, `exec(compile(...))`, `taskkill` e le build
PyInstaller/Nuitka. Le release vengono assemblate tramite lista consentita, con
SHA-256 e attestazione di provenienza registrati da GitHub.

Segnalazioni e codice: [GitHub](https://github.com/Deolink/ERITA)

Pagina del mod: (WORK IN PROGRESS)

## Licenza

[MIT](LICENSE)
