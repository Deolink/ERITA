# Migrazione dal vecchio installer `.exe`

> [!CAUTION]
> Anche le versioni source 0.9.1 e 0.9.2 sono temporaneamente sospese su
> Elden Ring 1.17.1 per incompatibilità dei banchi audio. Se una delle due è già
> stata applicata, usa la 0.9.3 e clicca su **Correggi audio (ripristina)**; se
> non fosse possibile, verifica l'integrità tramite Steam. Non installare la
> 0.8.4 come alternativa.

L'eseguibile delle versioni 0.8.x è stato dismesso. Non va usato per
installare, aggiornare né ripristinare il doppiaggio dopo un aggiornamento del gioco.

Il vecchio backup `sd.bdt.original` non registra da quale BHD/build proviene e copre
solo `sd.bdt`, anche se l'installer poteva modificare anche `sd_dlc02.bdt`.
Ripristinarlo sopra la patch 1.17.1 può mescolare file incompatibili.
Le versioni precedenti potevano anche lasciare `*.bk2.original` nelle cartelle
`movie` e `movie_dlc`; questi sidecar non hanno manifesto né hash del build.

## Procedura sicura

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Se la versione 0.9.1/0.9.2 ha creato un backup transazionale, apri la 0.9.3 e
   clicca su **Correggi audio (ripristina)**.
3. Se quel backup non esiste o il ripristino fallisce, su Steam apri **Libreria
   > Elden Ring > Proprietà > File installati > Verifica integrità dei file**.
4. Attendi che il recupero termini e avvia il gioco una volta per confermare i
   clic e l'audio originali prima di tornare in modalità online.
5. Solo dopo questa verifica, rimuovi i file extra terminanti in
   `.bdt.original` dentro `ELDEN RING\Game\sd` e i `*.bk2.original` in
   `ELDEN RING\Game\movie`/`movie_dlc`. Steam di solito non rimuove i file
   extra durante la verifica.

Il nuovo patcher blocca l'installazione finché trova un `.original` legacy.
Lo preserva e non tenta mai di indovinare se quel file appartiene al build attuale.

Se hai qualsiasi dubbio sullo stato dei file, ripeti la verifica di Steam. Non creare
un'eccezione in Defender e non ripristinare manualmente il vecchio backup.

Usa lo stesso account Windows per installare e ripristinare. Prima di spostare o rinominare
la libreria Steam, ripristina l'audio originale; se è già stata spostata con il doppiaggio
applicato, esegui una nuova verifica di integrità tramite Steam.

L'hotfix 0.9.3 non installa il doppiaggio né le cutscene opzionali. Non copiare le
cartelle `movie` o `movie_dlc` al suo interno; il vecchio pacchetto non ha ancora
un manifesto crittografico pubblico.
