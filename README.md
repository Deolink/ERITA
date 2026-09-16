# ERITA — Elden Ring Doppiaggio ITA (WORK IN PROGRESS)

Patcher per applicare il doppiaggio in Italiano a Elden Ring (PC).

Fork di [ERPT-BR](https://github.com/lorepamplona/ERPT-BR) di [@lorepamplona](https://github.com/lorepamplona), adattato per il doppiaggio italiano da [@Deolink](https://github.com/Deolink).

> [!CAUTION]
> **Installazione temporaneamente sospesa su Elden Ring 1.17.1.** Abbiamo
> individuato che il pacchetto audio usato dalle versioni 0.9.1 e 0.9.2
> sostituisce banchi più vecchi che rimuovono suoni presenti nel gioco attuale,
> incluse risorse brevi legate ai clic dell'interfaccia. **Non installare
> queste versioni.** Se le hai già installate, scarica la versione 0.9.3 e usa
> **Correggi audio (ripristina)**. Se il pulsante non fosse disponibile o il
> ripristino fallisse, usa **Steam > Proprietà > File installati > Verifica
> integrità**. Non entrare in modalità online prima di aver ripristinato.
> Consulta [il rapporto sull'incidente](docs/INCIDENTE-0.9.1.md).

Progetto di doppiaggio italiano per Elden Ring su PC. La versione 0.9.3 è un
**hotfix di sola recuperazione** per Elden Ring 1.17.1 (Steam BuildID
25080141): abbandona l'eseguibile proprio, impedisce nuove installazioni del
pacchetto interessato e ripristina i backup sicuri creati dalle versioni 0.9.x.

**Download:** (WORK IN PROGRESS)

Questa versione ha come obiettivo tecnico **Elden Ring 1.17.1 (Steam build
25080141)** e abbandona l'eseguibile proprietario che causava avvisi degli antivirus.
La coppia patch/BuildID è stata identificata, ma la pubblicazione stabile dipende ancora
dal test descritto in [Convalida in sospeso](#convalida-in-sospeso).

## La modalità online continua a funzionare?

In questo momento, **non usare il doppiaggio in modalità online**. La verifica ha
trovato incompatibilità di banchi e di integrità nel metodo diretto delle
versioni 0.9.1/0.9.2. Ripristina prima i file originali, verifica l'audio
originale nel gioco e solo dopo torna in modalità online.

L'obiettivo futuro resta evitare Mod Engine 3, l'iniezione di DLL e modifiche
all'Easy Anti-Cheat. Questo non è una promessa di compatibilità per il
pacchetto attualmente sospeso. Il progetto tornerà ad annunciare il supporto
online solo dopo un test reale di menu, battute, cutscene e sessione con l'EAC
sulla release corretta.

ERITA **non usa Mod Engine 3**, non inietta DLL nel gioco, non disattiva l'Easy
Anti-Cheat e non cambia il modo di avviare il gioco. Dopo aver installato il doppiaggio,
apri Elden Ring normalmente tramite Steam.

Il patcher sostituisce solo l'audio dentro i file `sd*.bdt` già usati dal gioco.
Questa architettura preserva l'avvio online normale. Poiché il servizio online
e le regole anti-cheat appartengono a terzi e possono cambiare, il progetto non
promette un rischio esterno assolutamente pari a zero. Il patcher è già stato validato
sui file reali del build target installato; manca ancora il test di apertura, login e
sessione online con l'Easy Anti-Cheat.

## Nuovo metodo di installazione

L'hotfix 0.9.3 non contiene un `.exe` creato o impacchettato dal progetto. Porta con sé:

- tutto il codice sorgente Python visibile;
- script `.cmd` inclusi come testo aperto per l'audit;
- dipendenze ufficiali in wheel, con versioni e SHA-256 bloccati;
- il verificatore e il ripristinatore transazionale dei file originali.

L'utente vede un solo punto di ingresso: `ERITA.cmd`. Al primo utilizzo verifica
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

## Recupero su Windows

Finché l'installazione resta sospesa, usa solo la versione 0.9.3 per il
recupero. Blocca nuove installazioni prima di scaricare il payload o modificare
il gioco e mette in evidenza **Correggi audio (ripristina)**. Se non ci fosse un
backup valido, esegui la verifica di integrità di Steam. Non usare le versioni
0.8.4, 0.9.1 o 0.9.2 come alternativa: contengono lo stesso vecchio pacchetto
audio.

## Installazione su Windows (sospesa)

Una migrazione a C#, Rust o un altro linguaggio non rimuoverebbe da sola gli avvisi:
tornerebbe a creare un eseguibile proprietario senza reputazione o firma del
codice. Per questo l'alternativa a un clic mantiene aperto il codice del mod e
delega solo l'installazione dell'interprete a canali ufficiali autenticati.

Se hai già usato il vecchio `.exe`, esegui prima la [migrazione sicura](MIGRACAO.md).

### Recupero: un unico file

1. Per recuperare un'installazione interessata, scarica
   `ERITA-v0.9.3-source-win64.zip` dalla pagina
   [Releases](https://github.com/Deolink/ERITA/releases). Non usare lo ZIP
   automatico "Source code", perché non contiene le dipendenze offline.
2. Estrai l'intero ZIP in una cartella normale.
3. Fai doppio clic su `ERITA.cmd`. Se il Python corretto non è
   presente, lo script installa la versione ufficiale nel tuo profilo; poi prepara
   l'ambiente e apre il patcher.
4. Seleziona la cartella `ELDEN RING\Game` e clicca su **Correggi audio
   (ripristina)**.
5. Attendi la conferma che i BDT originali sono stati ripristinati e
   verificati. Se non ci fosse un backup valido o si verificasse un errore, usa
   la verifica di integrità di Steam.
6. Apri prima il gioco per verificare i clic e l'audio originali. Solo dopo
   questa conferma torna in modalità online.

Per aprire di nuovo l'hotfix di recupero, usa sempre lo stesso `ERITA.cmd`.

Non eseguire il patcher come amministratore. Se Windows nega la scrittura, usa una
libreria Steam scrivibile dal tuo account o modifica solo il permesso della cartella
del gioco; il programma non tenta mai di elevarsi da solo.

La 0.9.3 si ferma prima di acquisire il payload vocale. Non scarica né applica
l'asset audio v0.8.1 sospeso.

Una copia di backup interrotta può lasciare una cartella nascosta
`.xxxxxxxxxxxx-xxxxxxxx` accanto ai backup. Il patcher registra il percorso esatto
e la preserva; rimuovila manualmente solo dopo aver confermato che non è l'unico
backup utile.

## Diagnostica di compatibilità e blocchi

Una versione del gioco fuori target, come la 1.17.0, non appare più come
un'installazione bloccata senza spiegazioni: il patcher mostra il BuildID
rilevato, il BuildID supportato, la fase in cui si è interrotto e un codice
stabile come `ERPT-COMPAT-001`. Il rifiuto avviene prima di caricare o
modificare i file audio.

Il pulsante **Diagnostica** resta disponibile anche durante un'operazione.
Genera localmente un report JSON con versione del patcher, BuildID già
identificato, fase, tempo trascorso in quella fase, ultimo avanzamento,
sistema e log recenti. In caso di errore, la spiegazione appare subito mentre
questo report viene preparato in background.
Il report non crea campi per nome utente, percorso completo, SteamID, salvataggi
o contenuto del manifesto e rimuove dai testi di errore pattern noti di questi
dati. La diagnostica inoltre non apre né calcola l'hash dei file del gioco.
Rivedi comunque il contenuto prima di pubblicarlo.

Niente viene inviato automaticamente. Nella finestra del report, l'utente può
rivedere, copiare, salvare o cliccare su **Apri segnalazione**. Quest'ultimo
pulsante si limita a copiare la diagnostica e ad aprire il
[modulo di compatibilità](https://github.com/Deolink/ERITA/issues/new?template=compatibilidade.yml);
l'invio resta manuale e la issue sarà pubblica. Non allegare salvataggi né file
del gioco.

## Backup, ripristino e aggiornamenti del gioco

La 0.9.3 rifiuta qualsiasi nuova applicazione. Per ripristinare, collega il
backup al fingerprint del BHD/build, autentica il backup e lo stato attuale,
prepara copie temporanee, registra un journal di recupero e rilegge il
risultato prima di annunciare il successo. Convalida inoltre gli hash salted
del BHD, in previsione di una futura applicazione che potrà creare backup o
sostituire i BDT.

Il backup esistente si trova fuori dalla cartella del gioco, in
`%LOCALAPPDATA%\ERITA\backups`, ed è collegato al fingerprint del build. Un
backup di una versione precedente non viene mai ripristinato su un BHD nuovo.

Ripristina l'audio originale **prima di spostare o rinominare la libreria Steam**. Se
la libreria è già stata spostata mentre il doppiaggio era applicato, usa la verifica
di integrità di Steam prima di installare di nuovo; il patcher cerca i manifest
dei percorsi precedenti e rifiuta di trasformare l'audio doppiato in un nuovo baseline.
Usa sempre lo stesso account Windows per installare, aggiornare e ripristinare il mod.
I backup restano nel profilo di quell'account e non coordinano operazioni avviate da
un altro utente dello stesso computer.

Quando Steam aggiorna Elden Ring, usa **Proprietà > File installati >
Verifica integrità dei file** e attendi una versione di ERITA che abbia come
target il nuovo BuildID. Se un backup sicuro di un altro build impedisce la creazione
del nuovo baseline, conferma prima l'audio originale e sposta quella cartella di
backup specifica altrove; il patcher non la cancella mai automaticamente.
Se c'è una transazione interrotta, il messaggio elenca anche i file
privati `.rollback`/`.displaced` che devono essere preservati nella stessa quarantena,
fuori da `Game\sd`, per non lasciare residui voluminosi né perdere le prove per il recupero.
Anche le copie `.erita-stage-*`/`.erita-restore-*` lasciate da un'interruzione
vengono preservate e hanno il percorso registrato per una pulizia manuale sicura.

## Limiti di questo hotfix

L'hotfix pubblico è limitato al Steam BuildID 25080141 e recupera solo i
backup 0.9.x corrispondenti a quel fingerprint. Non installa battute, BNK, WEM
né cutscene `.bk2`. Le cartelle `movie`/`movie_dlc` accanto all'installer
restano rifiutate; il vecchio pacchetto opzionale non possiede un manifesto
crittografico pubblico.

## Convalida in sospeso

Il bootstrap, il rollback e l'installer distribuito come sorgente hanno test
automatizzati. L'audit sull'installazione reale ha confermato che il backup
originale è integro e ripristinabile; ha anche mostrato che il vecchio
pacchetto rimuove contenuto dall'attuale `cs_main.bnk` e lascia 8.976 risorse
fuori dagli hash salted del BHD.

Le versioni `v0.9.1` e `v0.9.2` non devono essere considerate installabili. La
prossima release funzionale potrà essere promossa solo dopo aver ricostruito i
banchi sulla versione 1.17.1 e completato test reali di menu, battute,
cutscene, ripristino e sessione online con l'EAC.

## Sviluppo e test

```text
python -m pip install --require-hashes --only-binary=:all: -r patcher/requirements-win64.lock
python -m unittest discover -s tests -v
```

La CI rifiuta il ritorno del launcher dinamico, di `exec(compile(...))`, di
`taskkill` e di build PyInstaller/Nuitka. Le release vengono assemblate tramite lista
consentita e pubblicano un unico ZIP proprio, con digest SHA-256 e attestazione di
provenienza registrati da GitHub. La 0.9.3 viene pubblicata come Latest solo in
quanto recupero sicuro; le release funzionali restano pre-release finché lo
smoke test reale non sarà completato.

Segnalazioni e codice: [GitHub](https://github.com/Deolink/ERITA)

Pagina del mod: (WORK IN PROGRESS)

## Licenza

[MIT](LICENSE)
