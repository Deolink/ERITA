# Migrazione dal vecchio installer `.exe`

> [!IMPORTANT]
> L'incidente delle versioni 0.9.1 e 0.9.2 è stato corretto nella **0.9.4** e la
> correzione resta nella **0.9.5** per Elden Ring 1.17.1 (Steam BuildID
> `25080141`). Non usare la 0.8.4, la 0.9.1 o la 0.9.2 come alternativa: usano
> tutte il vecchio pacchetto di banchi.

L'eseguibile delle versioni 0.8.x è stato dismesso. Non va usato per
installare, aggiornare né ripristinare il doppiaggio dopo un aggiornamento del
gioco.

Il vecchio backup `sd.bdt.original` non registra da quale BHD/build proviene e
copre solo `sd.bdt`, anche se l'installer poteva modificare anche
`sd_dlc02.bdt`. Ripristinarlo sopra la patch 1.17.1 può mescolare file
incompatibili. Le versioni precedenti potevano anche lasciare `*.bk2.original`
in `movie` e `movie_dlc`; questi file aggiuntivi non hanno manifesto né hash
del build.

## Procedura sicura

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Scarica solo `ERITA-v0.9.5-Windows.zip` dalla pagina Releases ed estrai
   l'intero ZIP. (ERITA non ha ancora una release pubblicata: il pacchetto
   audio italiano è in lavorazione.)
3. Apri `ERITA.cmd` e clicca su **Correggi audio (ripristina)** se esiste un
   backup transazionale valido delle versioni 0.9.x.
4. Se quel backup non esiste o il ripristino fallisce, su Steam apri **Libreria
   > Elden Ring > Proprietà > File installati > Verifica integrità dei file**.
5. Avvia il gioco una volta e conferma che l'audio originale funziona.
6. Apri di nuovo `ERITA.cmd` e clicca su **Installa doppiaggio**.

Solo dopo aver confermato il recupero, rimuovi i file aggiuntivi che terminano
in `.bdt.original` dentro `ELDEN RING\Game\sd` e i `*.bk2.original` in
`ELDEN RING\Game\movie`/`movie_dlc`. Steam può conservare i file aggiuntivi
durante la verifica.

Il patcher attuale blocca l'installazione finché trova un `.original` legacy.
Preserva il file e non tenta mai di indovinare se appartiene al build attuale.

Non creare un'eccezione in Defender, non ripristinare manualmente un vecchio
backup e non eseguire il patcher come amministratore. Usa lo stesso account
Windows per installare e ripristinare. Prima di spostare o rinominare la
libreria Steam, ripristina l'audio originale; se è già stata spostata con il
doppiaggio applicato, verifica l'integrità tramite Steam.

Il pacchetto 0.9.5 installa audio WEM/BNK. Non copiarci le vecchie cartelle
`movie` o `movie_dlc`: il pacchetto opzionale di cutscene non ha ancora un
manifesto crittografico pubblico e verrà rifiutato.
