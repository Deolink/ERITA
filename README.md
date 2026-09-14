# ERITA — Elden Ring Dublagem ITA (WORK IN PROGRESS)

Patcher per applicare il doppiaggio in Italiano a Elden Ring (PC).

Fork di [ERPT-BR](https://github.com/lorepamplona/ERPT-BR) di [@lorepamplona](https://github.com/lorepamplona), adattato per il doppiaggio italiano da [@Deolink](https://github.com/Deolink).

**Download:** (WORK IN PROGRESS)

Questa versione candidata ha come obiettivo tecnico **Elden Ring 1.17.1 (Steam build
25080141)** e abbandona l'eseguibile proprietario che causava avvisi degli antivirus.
La coppia patch/BuildID è stata identificata, ma la pubblicazione stabile dipende ancora
dal test descritto in [Convalida in sospeso](#convalida-in-sospeso).

## La modalità online continua a funzionare?

ERPT-BR **non usa Mod Engine 3**, non inietta DLL nel gioco, non disattiva l'Easy
Anti-Cheat e non cambia il modo di avviare il gioco. Dopo aver installato il doppiaggio,
apri Elden Ring normalmente tramite Steam.

Il patcher sostituisce solo l'audio dentro i file `sd*.bdt` già usati dal gioco.
Questa architettura preserva l'avvio online normale. Poiché il servizio online
e le regole anti-cheat appartengono a terzi e possono cambiare, il progetto non
promette un rischio esterno assolutamente pari a zero. Il patcher è già stato validato
sui file reali del build target installato; manca ancora il test di apertura, login e
sessione online con l'Easy Anti-Cheat.

## Nuovo metodo di installazione

La release del mod non contiene un `.exe` creato o impacchettato dal progetto. Include:

- tutto il codice sorgente Python visibile;
- script `.cmd` inclusi come testo aperto per l'audit;
- dipendenze ufficiali in wheel, con versioni e SHA-256 bloccati;
- metadati fissi di URL, dimensione e SHA-256 per autenticare il pacchetto audio.

L'utente vede un solo punto di ingresso: `ERPT-BR.cmd`. Al primo utilizzo verifica
un'installazione compatibile, installa esattamente Python 3.13.15 x64 nel profilo
dell'utente quando necessario, prepara l'ambiente e apre il patcher. Negli utilizzi
successivi, lo stesso file convalida rapidamente l'ambiente e apre l'interfaccia senza
reinstallare tutto. I due script ausiliari si trovano nella cartella `interno` e non
vanno eseguiti direttamente.

Il flusso usa prima il pacchetto esatto `Python.Python.3.13` di WinGet; solo se
WinGet non è disponibile, scarica l'installer ufficiale della Python Software
Foundation e ne convalida dimensione, SHA-256, firma Authenticode ed editore prima
di eseguirlo. Se WinGet è presente ma fallisce, il bootstrap si ferma e mostra
l'errore invece di cambiare silenziosamente origine. Non richiede elevazione, non
aggiunge Python al `PATH` e usa solo i wheel inclusi nello ZIP. Se un Python
compatibile è già installato, viene trattato come base fidata dall'utente. In ogni
caso, il `python.exe` non è prodotto dal mod.

Una migrazione a C#, Rust o un altro linguaggio non rimuoverebbe da sola gli avvisi:
tornerebbe a creare un eseguibile proprietario senza reputazione o firma del
codice. Per questo l'alternativa a un clic mantiene aperto il codice del mod e
delega solo l'installazione dell'interprete a canali ufficiali autenticati.

## Installazione su Windows

Se hai già usato il vecchio `.exe`, esegui prima la [migrazione sicura](MIGRACAO.md).

### Installazione e uso: un unico file

1. Scarica `ERPT-BR-v0.9.1-source-win64.zip` dalla pagina
   [Releases](https://github.com/lorepamplona/ERPT-BR/releases). Non usare lo ZIP
   automatico "Source code", perché non contiene le dipendenze offline.
2. Estrai l'intero ZIP in una cartella normale.
3. Fai doppio clic su `ERPT-BR.cmd`. Se il Python corretto non è
   presente, lo script installa la versione ufficiale nel tuo profilo; poi prepara
   l'ambiente e apre il patcher.
4. Seleziona `ELDEN RING\Game` e installa.
5. Al termine, chiudi il patcher e apri il gioco normalmente tramite Steam.

Per aprire o riparare ERPT-BR in seguito, usa sempre lo stesso `ERPT-BR.cmd`.

Non eseguire il patcher come amministratore. Se Windows nega la scrittura, usa una
libreria Steam scrivibile dal tuo account o modifica solo il permesso della cartella
del gioco; il programma non tenta mai di elevarsi da solo.

Al primo utilizzo, i dati vocali (circa 560 MiB) vengono scaricati
dall'asset v0.8.1 e autenticati tramite dimensione e SHA-256 fissi
`d66bb45093e911202f80cebac44650063e27da2cba41a78760b10e4d82d81d0c`.
Dopo l'estrazione, ogni percorso, dimensione e byte partecipa anche al digest
dell'albero `587533f29239d8dbe2131573e6e86a2452b272e76983f6cfef1a332d7b046417`.
Restano in cache per le installazioni successive, ma il contenuto viene rivalidato
crittograficamente prima dell'uso.
Se uno scambio della cache viene interrotto, gli alberi `.extract-*`/`.old-*` vengono
preservati in quarantena invece di essere cancellati ricorsivamente. Dopo aver confermato
un'installazione corretta, possono essere spostati fuori dalla cache e rimossi
manualmente per recuperare spazio.

Allo stesso modo, una copia di backup interrotta può lasciare una cartella nascosta
`.xxxxxxxxxxxx-xxxxxxxx` accanto ai backup. Il patcher registra il percorso esatto
e la preserva; rimuovila manualmente solo dopo aver confermato che non è l'unico
backup utile.

## Backup e aggiornamenti del gioco

Prima di sostituire qualsiasi file, il patcher:

1. convalida il BHD installato e tutti gli offset rispetto al BDT attuale;
2. richiede che il 100% dei 9.241 file del payload trovi slot compatibili e
   convalida l'intero piano prima di scrivere;
3. crea un backup di **tutti** i BDT audio caricati, inclusi quelli che il
   payload attuale non modifica ancora;
4. applica il doppiaggio su copie temporanee;
5. rilegge e confronta ogni regione;
6. registra un journal di recupero e solo dopo scambia le copie con i file
   attivi senza sovrascrivere un file che riappaia durante l'operazione;
7. ricalcola lo SHA-256 di ogni BDT modificato prima di annunciare il successo.

Riserva alcuni GiB liberi. Il backup si trova fuori dalla cartella del gioco, in
`%LOCALAPPDATA%\ERPT-BR\backups`, ed è collegato al fingerprint del build. Un
backup di una versione precedente non viene mai ripristinato su un BHD nuovo.

Ripristina l'audio originale **prima di spostare o rinominare la libreria Steam**. Se
la libreria è già stata spostata mentre il doppiaggio era applicato, usa la verifica
di integrità di Steam prima di installare di nuovo; il patcher cerca i manifest
dei percorsi precedenti e rifiuta di trasformare l'audio doppiato in un nuovo baseline.
Usa sempre lo stesso account Windows per installare, aggiornare e ripristinare il mod.
I backup restano nel profilo di quell'account e non coordinano operazioni avviate da
un altro utente dello stesso computer.

Quando Steam aggiorna Elden Ring, usa **Proprietà > File installati >
Verifica integrità dei file** e attendi una versione di ERPT-BR che abbia come
target il nuovo BuildID. Se un backup sicuro di un altro build impedisce la creazione
del nuovo baseline, conferma prima l'audio originale e sposta quella cartella di
backup specifica altrove; il patcher non la cancella mai automaticamente.
Se c'è una transazione interrotta, il messaggio elenca anche i file
privati `.rollback`/`.displaced` che devono essere preservati nella stessa quarantena,
fuori da `Game\sd`, per non lasciare residui voluminosi né perdere le prove per il recupero.
Anche le copie `.erptbr-stage-*`/`.erptbr-restore-*` lasciate da un'interruzione
vengono preservate e hanno il percorso registrato per una pulizia manuale sicura.

## Limiti di questo aggiornamento

Il motore accetta dinamicamente le coppie `sd.bhd`/`sd.bdt` e `sd_dlcNN.bhd`/
`sd_dlcNN.bdt`, ma l'installer pubblico è deliberatamente limitato al build
Steam 25080141. Le nuove battute del Tarnished Pack che non fanno ancora parte del
payload restano nella lingua originale; l'installer non le presenta come doppiate.

Le cutscene `.bk2` non vengono installate in questa candidata. Il vecchio pacchetto
opzionale non ha un manifesto pubblico che fissi percorsi, dimensioni e SHA-256; per
questo i file `.bk2` presenti direttamente nelle cartelle `movie` o `movie_dlc` accanto
all'installer vengono rifiutati prima di qualsiasi modifica. La funzione tornerà
solo dopo la pubblicazione e la convalida di quel manifesto.

## Convalida in sospeso

Il motore, il rollback e l'installer distribuito come sorgente hanno test automatizzati.
Il payload pubblico reale è stato scaricato e convalidato per intero: 8.969 WEM + 272 BNK,
604.911.847 byte. Su questa macchina, il bootstrap è stato eseguito anche senza Python
preinstallato e lo ZIP finale è passato dal dry-run contro i BHD/BDT reali del
Steam build 25080141: i 9.241 file sono stati autenticati e corrispondono a 9.105
slot fisici unici, senza file privi di destinazione. L'applicazione completa è stata
eseguita anche su una copia temporanea dei BHD/BDT reali: tutti gli slot sono stati riletti
e il ripristino finale ha coinciso byte per byte con lo stato precedente, senza residui.
Mancano ancora i test che modificano o eseguono l'installazione usata da Steam:

- applicazione seguita da ripristino nella libreria Steam vera e propria;
- apertura del gioco e verifica delle battute;
- login, summon/invasione e chiusura di una sessione online con l'EAC normale.

Per questo, tratta `v0.9.1` come candidata fino al completamento di questo smoke test. Il
patcher blocca altri BuildID e non modifica eseguibile, DLL, save, launcher o
Easy Anti-Cheat.

## Sviluppo e test

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

La CI rifiuta il ritorno del launcher dinamico, di `exec(compile(...))`, di
`taskkill` e di build PyInstaller/Nuitka. Le release vengono assemblate tramite lista
consentita e pubblicano un unico ZIP proprio, con digest SHA-256 e attestazione di
provenienza registrati da GitHub. Finché lo smoke test reale è in sospeso, il
workflow pubblica la versione come pre-release.

Segnalazioni e codice: [GitHub](https://github.com/Deolink/ERITA)

Pagina del mod: (WORK IN PROGRESS)

## Licenza

[MIT](LICENSE)
