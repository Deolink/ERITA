# Politica di sicurezza

## Modello di distribuzione

- Il progetto non pubblica un eseguibile proprio.
- La release Windows contiene il sorgente del patcher, script `.cmd` trasparenti e
  wheel fissati. PyCryptodome include codice nativo verificato, ma nulla viene
  copiato o iniettato come DLL nel gioco.
- Il passaggio interno `interno/INSTALAR_AMBIENTE.cmd` prepara l'ambiente senza scaricare
  codice: il codice del progetto e le dipendenze del mod provengono solo dallo ZIP
  pubblicato. L'interprete e la libreria standard provengono da un'installazione compatibile
  preesistente, che fa parte della base fidata dall'utente. Non esiste `exec`,
  `eval` né download di codice Python da `main`.
- L'unico punto di ingresso pubblico, `ERITA.cmd`, può installare esattamente Python
  3.13.15 x64 nel profilo dell'utente. Tenta prima il pacchetto esatto
  `Python.Python.3.13`, versione `3.13.15`, fonte `winget`, ambito `user` e
  architettura `x64`, senza saltare la verifica hash di WinGet. Solo quando
  WinGet è assente, scarica
  `https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe`.
- Prima di eseguire questo installer ufficiale, il bootstrap richiede esattamente
  29.452.944 byte, SHA-256
  `edec09c4853aeae9ac36efb8c9f95b6b8e2fee65eee56d9767a8b7c69c574403`,
  una firma Authenticode valida e l'editore
  `CN=Python Software Foundation, O=Python Software Foundation, L=Beaverton, S=Oregon, C=US`.
  Installa solo nel profilo attuale, non aggiunge Python al `PATH` e non tenta
  l'autoelevazione. L'eseguibile ufficiale non è incluso nello ZIP del mod.
- I metadati del payload legacy `patch_data_v081.zip` restano fissati per
  l'audit, ma l'hotfix 0.9.3 blocca il flusso prima di scaricarlo o applicarlo.
  Una futura versione installabile dovrà pubblicare e validare il nuovo payload
  tramite HTTPS, dimensione, SHA-256, struttura ZIP e digest canonico dei file.
- Quando l'ambiente Python è assente o non valido, l'installer lo ricrea usando
  solo i wheel locali verificati. Un ambiente integro viene riutilizzato; il flusso
  non termina processi, non si autoeleva e non si autoaggiorna.
- Il patcher non usa Mod Engine 3, non avvia Elden Ring, non inietta librerie,
  non modifica l'EAC e non cambia il modo in cui il gioco viene avviato tramite Steam.
- Il vecchio pacchetto opzionale di cutscene viene rifiutato: non possiede ancora un
  manifesto pubblico con percorsi, dimensioni e SHA-256 fissati.

## Integrità della release

Ogni release source di questa nuova linea pubblica un unico ZIP proprio. GitHub
registra il digest SHA-256 dell'asset e genera un'attestazione di provenienza tramite GitHub
Actions. Per verificare un artefatto con la CLI di GitHub:

```text
gh attestation verify ERITA-v0.9.3-source-win64.zip --repo Deolink/ERITA
```

Il workflow usa dipendenze bloccate per SHA di commit e non sovrascrive mai un
asset di release esistente.

Questi controlli partono da una normale sessione Windows, senza un altro processo
malevolo già in esecuzione come lo stesso utente. Un processo con tale autorità potrebbe
già alterare il sorgente estratto, l'ambiente locale, i backup e i file del
gioco; l'installer non tenta di sostituire le protezioni dell'account o del sistema.

## Dati locali

Il programma non raccoglie telemetria né invia file dell'utente. L'hotfix 0.9.3
non scarica payload audio. Il bootstrap con un clic può accedere a WinGet o a
`python.org` per installare il Python ufficiale, come descritto sopra. I pulsanti
**Dettagli** e **Apri segnalazione** chiedono al browser predefinito di aprire
GitHub solo dopo un clic esplicito; il report non viene allegato all'URL. I
backup audio, gli ambienti isolati e la cache restano nel profilo locale
dell'utente.
Gli alberi di cache abbandonati vengono preservati con nomi `.extract-*`/`.old-*`;
il programma non tenta l'eliminazione ricorsiva di un percorso che potrebbe essere stato
sostituito da una junction. L'interfaccia registra il percorso esatto per una pulizia manuale successiva.
Le cartelle di staging dei backup interrotti seguono la stessa regola: vengono preservate
e segnalate, mai rimosse ricorsivamente in modo automatico.

La diagnostica di supporto viene elaborata localmente; solo la condivisione è
opzionale. Usa un elenco chiuso di campi e rimuove dai testi pattern noti di
percorsi, identità, e-mail, SteamID e segreti. Per evitare che una sostituzione
concorrente della junction faccia accedere la diagnostica a un'altra destinazione,
il report non apre, elenca né calcola l'hash dei file del gioco. Il pulsante
**Apri segnalazione** copia il report e apre un modulo pubblico su GitHub, ma
non esegue mai l'upload o la pubblicazione automatica. L'utente deve rivedere e
inviare il contenuto manualmente.

## Segnalare una vulnerabilità

Non pubblicare dettagli sfruttabili in una issue. Usa la funzione **Security >
Report a vulnerability** del repository quando è disponibile, oppure contatta
privatamente il maintainer indicato nel profilo del progetto.
