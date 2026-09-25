# Politica di sicurezza

## Modello di distribuzione

- Il progetto non pubblica un eseguibile proprio.
- L'unico download destinato all'utente sarà `ERITA-v0.9.5-Windows.zip`
  (nessuna release è ancora pubblicata: il pacchetto audio italiano è in
  lavorazione). Contiene il codice sorgente del patcher, script `.cmd`
  trasparenti, dipendenze bloccate e il payload audio autenticato.
- Gli ZIP automatici **Source code** di GitHub non sono installer e non
  contengono il pacchetto completo.
- PyCryptodome include codice nativo verificato, ma nulla viene copiato o
  iniettato come DLL nel gioco.
- Il passaggio interno `interno/INSTALAR_AMBIENTE.cmd` prepara l'ambiente usando
  solo i wheel inclusi e verificati. Non esiste `exec`, `eval` né download di
  codice Python da `main`.
- L'unico punto di ingresso pubblico, `ERITA.cmd`, può installare esattamente il
  Python 3.13.15 x64 ufficiale nel profilo dell'utente. Tenta prima il pacchetto
  `Python.Python.3.13`, versione `3.13.15`, fonte `winget`, ambito `user` e
  architettura `x64`, senza saltare la verifica hash di WinGet.
- Solo quando WinGet è assente, il bootstrap scarica l'installer ufficiale da
  `python.org`. Prima di eseguirlo richiede 29.452.944 byte, SHA-256
  `edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403`, una firma
  Authenticode valida e l'editore Python Software Foundation.
- Python viene installato nel profilo attuale, non viene aggiunto al `PATH` e non
  c'è nessun tentativo di autoelevazione. L'eseguibile ufficiale non è incluso
  nello ZIP del mod.

## Integrità del payload audio

Prima dell'uso il patcher convalida il payload rispetto ai valori fissati nel
codice. Oggi quei valori sono quelli del payload PT-BR dell'upstream,
ricostruito sui banchi originali di Elden Ring 1.17.1 (Steam BuildID
`25080141`); il payload italiano avrà valori propri:

- formato distribuito dalla 0.9.5: cartella piatta `patch_data`, senza archivi
  audio compressi annidati;
- SHA-256 canonico dell'albero:
  `8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb`;
- inventario: 8.969 WEM e 272 alias BNK, 9.241 file in totale;
- dimensione decompressa: `605706607` byte;
- file più grande: `74956066` byte.

Qualunque differenza di dimensione, hash, struttura, inventario o percorso fa
rifiutare il payload prima di scrivere nel gioco.

L'archivio di origine usato per assemblare quell'albero resta fissato a
588.468.447 byte e SHA-256
`430e9693a9b3313826e9f7c890cf592eb5b468d145bb405e8a4586002b877680`. È solo
un input autenticato del workflow e non viene inserito nello ZIP consegnato
all'utente.

Per provare audio italiano non ancora fissato esiste la variabile di sviluppo
`ERITA_DEV_UNSAFE_SKIP_PAYLOAD_PIN`, che salta solo i confronti con i valori
fissati (restano attivi i controlli strutturali). Finché resta nel codice,
`tools/verify_source_release.py` rifiuta qualunque release.

## Easy Anti-Cheat e modalità online

Il patcher non usa Mod Engine 3, non avvia Elden Ring, non inietta librerie, non
modifica l'Easy Anti-Cheat e non cambia il modo di avviare il gioco tramite
Steam. La correzione audio usata dalla 0.9.5 è stata convalidata dal progetto
originale in una sessione reale della 0.9.4, con il suo payload PT-BR, EAC e
connessione online attivi. La 0.9.5 cambia solo il modo di distribuire lo stesso
payload autenticato.

Le modifiche ai dati nei BDT non sono accompagnate da una riscrittura o
rifirma degli indici BHD. Di conseguenza le risorse modificate (8.973 nel
payload PT-BR) non corrispondono più agli hash salted originali. In modalità di
produzione il patcher consente solo queste divergenze quando appartengono
esattamente agli slot del piano autenticato; una divergenza fuori da questo
perimetro interrompe l'installazione. Il test online non trasforma questo
limite in una garanzia di compatibilità o di assenza di rischio.

Un test riuscito non equivale a una garanzia permanente di rischio zero. Un
aggiornamento del gioco, dell'EAC o delle regole del servizio può cambiare il
risultato. Il supporto è limitato al gioco e al BuildID dichiarati nella
release.

## Integrità della release

Ogni release di questa linea pubblica un unico ZIP proprio destinato
all'utente. GitHub registra il digest SHA-256 dell'asset e genera
un'attestazione di provenienza tramite GitHub Actions. Per verificare il
pacchetto con la CLI di GitHub:

```text
gh attestation verify ERITA-v0.9.5-Windows.zip --repo Deolink/ERITA
```

Il workflow usa dipendenze bloccate per SHA di commit e non deve sovrascrivere
un asset di release esistente. L'hash finale del pacchetto Windows viene
pubblicato solo dopo il suo assemblaggio e la sua verifica.

## Dati locali e privacy

Il programma non raccoglie telemetria né invia file dell'utente. Il payload
audio accompagna il pacchetto completo e viene convalidato localmente. Il
bootstrap può accedere a WinGet o a `python.org` per installare il Python
ufficiale.

I pulsanti **Dettagli** e **Apri segnalazione** chiedono al browser predefinito
di aprire GitHub solo dopo un clic esplicito. La diagnostica viene elaborata
localmente, usa un elenco chiuso di campi e rimuove pattern noti di percorsi,
identità, e-mail, SteamID e segreti. Non apre, elenca né calcola l'hash dei file
del gioco. L'utente deve rivedere e inviare il contenuto manualmente.

Backup, ambienti isolati e cache restano nel profilo locale. Gli alberi
abbandonati e le transazioni interrotte vengono preservati e segnalati; il
programma non tenta l'eliminazione ricorsiva di un percorso che potrebbe essere
stato sostituito da una junction o da un altro reparse point.

Questi controlli partono da una normale sessione Windows, senza un altro
processo malevolo già in esecuzione come lo stesso utente. Un processo con
questa autorità potrebbe già alterare il sorgente estratto, l'ambiente locale, i
backup e il gioco.

## Segnalare una vulnerabilità

Non pubblicare dettagli sfruttabili in una issue. Usa **Security > Report a
vulnerability** nel repository quando è disponibile, oppure contatta
privatamente il maintainer indicato nel profilo del progetto.
