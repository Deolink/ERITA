# Politica di sicurezza

## Modello di distribuzione

- Il progetto non pubblica un eseguibile proprio.
- La versione 0.9.7 prevede due download destinati all'utente (nessuna release
  ERITA è ancora pubblicata: il pacchetto audio italiano è in lavorazione):
  `ERITA-v0.9.7-Windows.zip` per Windows x64 e
  `ERITA-v0.9.7-Linux-x86_64.tar.gz` per Linux x86_64 e Steam Deck in modalità
  desktop. Entrambi contengono il codice sorgente del patcher, un launcher
  trasparente, dipendenze bloccate e il payload audio autenticato.
- Gli archivi automatici **Source code** di GitHub non sono installer e non
  contengono il pacchetto completo.
- PyCryptodome include codice nativo verificato, ma nulla viene copiato o
  iniettato come DLL nel gioco.
- Il passaggio interno `interno/INSTALAR_AMBIENTE.cmd` prepara l'ambiente usando
  solo i wheel inclusi e verificati. Non esiste `exec`, `eval` né download di
  codice Python da `main`.
- L'unico punto di ingresso pubblico su Windows, `ERITA.cmd`, può installare
  esattamente il Python 3.13.15 x64 ufficiale nel profilo dell'utente. Tenta
  prima il pacchetto `Python.Python.3.13`, versione `3.13.15`, fonte `winget`,
  ambito `user` e architettura `x64`, senza saltare la verifica hash di WinGet.
- Solo quando WinGet è assente, il bootstrap scarica l'installer ufficiale da
  `python.org`. Prima di eseguirlo richiede 29.452.944 byte, SHA-256
  `edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403`, una firma
  Authenticode valida e l'editore Python Software Foundation.
- Python viene installato nel profilo attuale, non viene aggiunto al `PATH` e non
  c'è nessun tentativo di autoelevazione. L'eseguibile ufficiale non è incluso
  nello ZIP del mod.
- Su Linux, `ERITA.sh` rifiuta root e prepara tutto dentro il profilo
  dell'utente. Il pacchetto include e autentica il runtime Astral
  `python-build-standalone` 20260924, CPython 3.13.15 x86_64 senza
  free-threading, e wheel Linux fissati.
- La preparazione su Linux usa solo il runtime, il lock e i wheel inclusi, con
  `pip --no-index --require-hashes --only-binary=:all:`. Non richiede Python di
  sistema, `sudo` né rete, nemmeno al primo avvio.

## Integrità del payload audio

Prima dell'uso il patcher convalida il payload rispetto ai valori fissati nel
codice. Oggi quei valori sono quelli del payload PT-BR dell'upstream,
ricostruito sui banchi originali di Elden Ring 1.17.1 (Steam BuildID
`25080141`); il payload italiano avrà valori propri:

- formato distribuito dalla 0.9.5: cartella piatta `patch_data`, senza archivi
  audio compressi annidati;
- SHA-256 canonico dell'albero:
  `e97467e8ebbd1da87be96a44e4a2ee5694cd41c0bf592159b0570258d0b8460e`;
- inventario: 8.968 WEM e 272 alias BNK, 9.240 file in totale;
- dimensione decompressa: `605607009` byte;
- file più grande: `74956066` byte.

Qualunque differenza di dimensione, hash, struttura, inventario o percorso fa
rifiutare il payload prima di scrivere nel gioco.

L'archivio di origine usato per assemblare quell'albero resta fissato a
588.370.781 byte e SHA-256
`873a432f1f1a8a42fca0aa71610e019563b79da3772656c48280b31a80a858a6`. È solo
un input autenticato del workflow e non viene inserito nel pacchetto consegnato
all'utente.

Per provare audio italiano non ancora fissato esiste la variabile di sviluppo
`ERITA_DEV_UNSAFE_SKIP_PAYLOAD_PIN`, che salta solo i confronti con i valori
fissati (restano attivi i controlli strutturali). Finché resta nel codice,
`tools/verify_source_release.py` e `tools/verify_linux_release.py` rifiutano
qualunque release.

## Compatibilità dei file del gioco

L'`appmanifest` di Steam non è un'autorità di sicurezza e non autorizza né
blocca mai da solo un'installazione. Il patcher usa come autorità i file reali:

- richiede gli indici BHD e le coppie BDT del profilo omologato;
- controlla lo SHA-256 dei BHD e le dimensioni attese dei BDT nella verifica
  rapida;
- prima della prima scrittura controlla lo SHA-256 completo dei BDT vanilla;
- in reinstallazioni e ripristini accetta solo un baseline originale già
  autenticato e il risultato registrato da ERITA stesso.

Un manifesto assente, illeggibile o copiato non sostituisce né invalida un
profilo locale riconosciuto. In quei casi l'installazione del doppiaggio può
proseguire, ma Steam e l'online restano esplicitamente non confermati. Copiare
un manifesto esterno non aggira nessuna verifica dei file reali.

## Easy Anti-Cheat e modalità online

Il patcher non usa Mod Engine 3, non avvia Elden Ring, non inietta librerie, non
modifica l'Easy Anti-Cheat e non cambia il modo di avviare il gioco tramite
Steam. Il payload su cui si basa la 0.9.7 è stato convalidato su Windows dal
progetto originale, con il suo payload PT-BR, in una sessione reale della 0.9.4
con EAC e connessione online attivi. La 0.9.5 ha cambiato solo la distribuzione;
la 0.9.6 cambia solo l'autorità usata per riconoscere la compatibilità, con lo
stesso payload autenticato. La 0.9.7 porta l'installer su Linux e lascia
vanilla un effetto non verbale dell'animazione di Sellen; questa mitigazione
deve ancora essere confermata nella missione. La sessione su Windows non prova
il comportamento su Linux/Proton: l'online su Linux verrà dichiarato
supportato solo dopo la convalida in CI e un test fisico riproducibile.

Le modifiche ai dati nei BDT non sono accompagnate da una riscrittura o
rifirma degli indici BHD. Di conseguenza le risorse modificate non
corrispondono più agli hash salted originali. In modalità di produzione il
patcher consente solo queste divergenze quando appartengono esattamente agli
slot del piano autenticato; una divergenza fuori da questo perimetro
interrompe l'installazione. Il test online non trasforma questo limite in una
garanzia di compatibilità o di assenza di rischio.

Un test riuscito non equivale a una garanzia permanente di rischio zero. Un
aggiornamento del gioco, dell'EAC o delle regole del servizio può cambiare il
risultato. Il supporto è limitato al profilo reale dei file e al payload
dichiarati nella release. Il BuildID di Steam, quando disponibile, è
un'informazione ausiliaria e non una prova del contenuto installato.

## Integrità della release

La release 0.9.7 prevede uno ZIP per Windows e un `tar.gz` per Linux destinati
all'utente. GitHub registra il digest SHA-256 di ogni asset e genera
un'attestazione di provenienza tramite GitHub Actions. Per verificare i
pacchetti con la CLI di GitHub:

```text
gh attestation verify ERITA-v0.9.7-Windows.zip --repo Deolink/ERITA
gh attestation verify ERITA-v0.9.7-Linux-x86_64.tar.gz --repo Deolink/ERITA
```

Il workflow usa dipendenze bloccate per SHA di commit e non deve sovrascrivere
un asset di release esistente. Gli hash finali vengono pubblicati solo dopo
l'assemblaggio e la verifica dei due pacchetti.

## Dati locali e privacy

Il programma non raccoglie telemetria né invia file dell'utente. Il payload
audio accompagna il pacchetto completo e viene convalidato localmente. Su
Windows il bootstrap può accedere a WinGet o a `python.org` per installare il
Python ufficiale. Su Linux runtime e dipendenze sono inclusi nel `tar.gz` e il
primo avvio è offline.

I pulsanti **Dettagli** e **Apri segnalazione** chiedono al browser predefinito
di aprire GitHub solo dopo un clic esplicito. La diagnostica viene elaborata
localmente, usa un elenco chiuso di campi e rimuove pattern noti di percorsi,
identità, e-mail, SteamID e segreti. La generazione del report non avvia una
nuova lettura dei file del gioco e non ne include gli hash; le verifiche di
compatibilità dell'operazione sono separate. L'utente deve rivedere e inviare
il contenuto manualmente.

Backup, ambienti isolati e cache restano nel profilo locale. Su Linux il
supporto iniziale presume `ext4`; NTFS, exFAT e btrfs non sono ancora garantiti
senza un test specifico. Gli alberi abbandonati e le transazioni interrotte
vengono preservati e segnalati; il programma non tenta l'eliminazione ricorsiva
di un percorso che potrebbe essere stato sostituito da una junction o da un
altro reparse point.

Questi controlli partono da una normale sessione Windows o Linux, senza un
altro processo malevolo già in esecuzione come lo stesso utente. Un processo con
questa autorità potrebbe già alterare il sorgente estratto, l'ambiente locale, i
backup e il gioco.

## Segnalare una vulnerabilità

Non pubblicare dettagli sfruttabili in una issue. Usa **Security > Report a
vulnerability** nel repository quando è disponibile, oppure contatta
privatamente il maintainer indicato nel profilo del progetto.
