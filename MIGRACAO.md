# Migrazione dal vecchio installer `.exe`

L'eseguibile delle versioni 0.8.x è stato dismesso. Non va usato per
installare, aggiornare né ripristinare il doppiaggio dopo un aggiornamento del gioco.

Il vecchio backup `sd.bdt.original` non registra da quale BHD/build proviene e copre
solo `sd.bdt`, anche se l'installer poteva modificare anche `sd_dlc02.bdt`.
Ripristinarlo sopra la patch 1.17.1 può mescolare file incompatibili.
Le versioni precedenti potevano anche lasciare `*.bk2.original` nelle cartelle
`movie` e `movie_dlc`; questi sidecar non hanno manifesto né hash del build.

## Procedura sicura

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Su Steam, apri **Libreria > Elden Ring > Proprietà > File
   installati > Verifica integrità dei file**.
3. Attendi che Steam concluda e avvia il gioco una volta per confermare l'audio
   originale. Chiudi di nuovo il gioco.
4. Solo dopo questa verifica, rimuovi i file extra terminanti in
   `.bdt.original` dentro `ELDEN RING\Game\sd` e i `*.bk2.original` in
   `ELDEN RING\Game\movie`/`movie_dlc`. Steam di solito non rimuove i file
   extra durante la verifica.
5. Installa la versione source seguendo il [README](README.md): estrai l'intero ZIP
   e usa sempre `ERITA.cmd`. Al primo utilizzo installa, in quelli successivi apre
   ed inoltre ripara automaticamente un ambiente incompleto.

Il nuovo patcher blocca l'installazione finché trova un `.original` legacy.
Lo preserva e non tenta mai di indovinare se quel file appartiene al build attuale.

Se hai qualsiasi dubbio sullo stato dei file, ripeti la verifica di Steam. Non creare
un'eccezione in Defender e non ripristinare manualmente il vecchio backup.

Usa lo stesso account Windows per installare e ripristinare. Prima di spostare o rinominare
la libreria Steam, ripristina l'audio originale; se è già stata spostata con il doppiaggio
applicato, esegui una nuova verifica di integrità tramite Steam.

Le cutscene opzionali non vengono installate dalla candidata 0.9.1, poiché il vecchio pacchetto
non ha ancora un manifesto crittografico pubblico. Non copiare le cartelle `movie`
o `movie_dlc` nel nuovo installer.
