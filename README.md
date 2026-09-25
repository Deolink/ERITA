# ERITA — Elden Ring Doppiaggio ITA (WORK IN PROGRESS)

Patcher per applicare il doppiaggio in Italiano a Elden Ring (PC).

Fork di [ERPT-BR](https://github.com/lorepamplona/ERPT-BR) di [@lorepamplona](https://github.com/lorepamplona), adattato per il doppiaggio italiano da [@Deolink](https://github.com/Deolink).

> [!IMPORTANT]
> Il codice di ERITA è allineato alla versione **0.9.5** del progetto
> originale, che installa il doppiaggio su Elden Ring **1.17.1** (Steam BuildID
> `25080141`). I banchi audio vengono ricostruiti sui banchi originali di
> quella versione, per preservare i suoni aggiunti dal gioco, inclusi i clic
> dell'interfaccia che sparivano con le versioni 0.9.1 e 0.9.2. La 0.9.5
> distribuisce l'audio corretto in un pacchetto piatto, senza lo ZIP audio
> annidato.
>
> **Il pacchetto audio italiano non è ancora pronto**: le registrazioni sono in
> corso, quindi ERITA non ha ancora una release installabile.

## Download

**Download:** (WORK IN PROGRESS)

Quando sarà pubblicata una release, dalla pagina
[Releases](https://github.com/Deolink/ERITA/releases) andrà scaricato solo:

`ERITA-v0.9.5-Windows.zip`

È il pacchetto completo per l'utente: installer in codice sorgente, dipendenze
verificate e payload audio. Non scaricare gli ZIP automatici **Source code** di
GitHub e non provare a eseguire separatamente i file interni del payload.

## Installazione su Windows

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Estrai **tutto** il contenuto di `ERITA-v0.9.5-Windows.zip` in una cartella
   normale.
3. Fai doppio clic su `ERITA.cmd`.
4. Conferma la cartella `ELDEN RING\Game` rilevata tramite Steam oppure
   selezionala.
5. Clicca su **Installa doppiaggio** e attendi la conferma finale.
6. Apri il gioco normalmente tramite Steam.

L'utente vede un solo punto di ingresso: `ERITA.cmd`. Al primo utilizzo
verifica il pacchetto e prepara un ambiente isolato. Se necessario, installa il
CPython 3.13.15 x64 ufficiale nel profilo dell'utente. Negli utilizzi
successivi, lo stesso file apre l'interfaccia senza rifare un'installazione
valida.

Non eseguire il patcher come amministratore. Se Windows nega la scrittura,
chiudi il gioco e l'EAC e usa una libreria Steam scrivibile dal tuo account,
oppure modifica solo il permesso della cartella del gioco.

## Modalità online

La correzione audio mantenuta dalla 0.9.5 è stata testata dal progetto
originale ERPT-BR in una sessione reale sulla 0.9.4, con il **suo** pacchetto
audio PT-BR: gioco avviato normalmente da Steam, Easy Anti-Cheat e connessione
online attivi. Il test si è concluso con successo e i suoni dei clic hanno
continuato a funzionare. ERITA usa lo stesso metodo, ma non ha ancora un
pacchetto audio proprio da provare online. Il patcher non disattiva né modifica
l'EAC, non inietta DLL e non cambia il modo di avviare il gioco.

Il metodo diretto modifica dati dentro i BDT, ma non riscrive né rifirma gli
indici BHD. Per questo le risorse modificate non corrispondono più agli hash
salted originali (8.973 nel pacchetto PT-BR). L'installer accetta solo le
divergenze esatte del piano e del payload autenticati; qualunque differenza in
più viene rifiutata. Una sessione online riuscita non elimina questo limite
tecnico.

Quel risultato vale per la versione e la sessione testate: non è una garanzia
di rischio zero né di compatibilità con futuri aggiornamenti del gioco,
dell'EAC o delle regole del servizio. Se Steam aggiorna Elden Ring, ripristina
o verifica i file e attendi la conferma del supporto al nuovo BuildID.

## Cosa è cambiato nella 0.9.5

- l'audio ora si trova direttamente nella cartella `patch_data` del pacchetto
  estratto;
- non c'è più uno ZIP audio grande dentro lo ZIP da scaricare;
- l'interfaccia e il metodo di installazione restano gli stessi;
- il pacchetto resta un unico download con un unico punto di ingresso,
  `ERITA.cmd`;
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

Per riferimento, il payload PT-BR autenticato dell'upstream contiene 9.241
file: 8.969 WEM e 272 alias BNK, corrispondenti a 136 banchi fisici
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

Una versione del gioco fuori target, come la 1.17.0, non sembra più
un'installazione bloccata. Il patcher mostra il BuildID trovato, il BuildID
supportato, la fase in cui si è fermato e un codice stabile come
`ERITA-COMPAT-001`. Il rifiuto avviene prima di caricare o modificare l'audio.

Il pulsante **Diagnostica** genera localmente un report JSON con versione del
patcher, BuildID identificato, fase, tempo, avanzamento, sistema e log recenti.
Il report non include di proposito nome utente, percorso completo, SteamID,
salvataggi o contenuto del manifesto, e non apre né calcola l'hash dei file del
gioco. Rivedi comunque il contenuto prima di pubblicarlo.

Niente viene inviato automaticamente. Il pulsante **Apri segnalazione** si
limita a copiare la diagnostica e ad aprire il
[modulo di compatibilità](https://github.com/Deolink/ERITA/issues/new?template=compatibilidade.yml);
l'invio resta manuale e la issue sarà pubblica.

## Backup, ripristino e aggiornamenti

Il backup si trova in `%LOCALAPPDATA%\ERITA\backups` ed è collegato al
fingerprint del BHD e al BuildID del gioco. Il patcher autentica il backup,
prepara copie temporanee, registra un journal transazionale e rilegge il
risultato prima di annunciare il successo. Un backup di un altro build non
viene mai ripristinato sul gioco attuale.

Ripristina l'audio originale prima di spostare o rinominare la libreria Steam.
Usa lo stesso account Windows per installare e ripristinare. Se il gioco si
aggiorna, esegui la verifica di integrità di Steam e attendi una versione di
ERITA che riconosca il nuovo BuildID.

I file di una transazione interrotta (anche le copie `.erita-stage-*` e
`.erita-restore-*`) vengono preservati per la diagnostica; il programma non
cancella mai ricorsivamente un percorso che potrebbe essere stato sostituito da
un link o da una junction.

## Limiti attuali

- Windows x64 e versione Steam di Elden Ring;
- Elden Ring 1.17.1, Steam BuildID `25080141`;
- audio WEM/BNK; il vecchio pacchetto opzionale di cutscene `.bk2` resta
  rifiutato perché non ha un manifesto crittografico pubblico;
- le versioni future del gioco richiedono una convalida e una release
  specifiche.

## Sviluppo e test

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

Per avviare `ERITA.cmd` direttamente dal checkout serve una cartella
`patch_data` accanto allo script: vuota basta per aprire l'interfaccia e
usare il ripristino. Per provare file `.wem`/`.bnk` italiani non ancora
fissati nel manifesto del payload, mettili in `patch_data` e imposta la
variabile di sviluppo `ERITA_DEV_UNSAFE_SKIP_PAYLOAD_PIN=1`. Finché quella
variabile resta nel codice, `tools/verify_source_release.py` rifiuta qualunque
release.

La CI rifiuta il launcher dinamico, `exec(compile(...))`, `taskkill` e le build
PyInstaller/Nuitka. Le release vengono assemblate tramite lista consentita, con
SHA-256 e attestazione di provenienza registrati da GitHub.

Segnalazioni e codice: [GitHub](https://github.com/Deolink/ERITA)

Pagina del mod: (WORK IN PROGRESS)

## Licenza

[MIT](LICENSE)
