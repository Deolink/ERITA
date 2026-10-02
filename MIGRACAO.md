# Migrazione dal vecchio installer `.exe`

> [!IMPORTANT]
> L'incidente delle versioni 0.9.1 e 0.9.2 è stato corretto nella **0.9.4** e la
> correzione resta nella **0.9.7** per Elden Ring 1.17.1 (Steam BuildID
> ausiliario `25080141`). Non usare la 0.8.4, la 0.9.1 o la 0.9.2 come
> alternativa: usano tutte il vecchio pacchetto di banchi.

> [!WARNING]
> Non serve scaricare, copiare né distribuire `appmanifest_1245620.acf`. Chi ha
> già messo quel file non verrà bloccato per questo, ma contiene solo metadati
> locali di Steam e non aggiorna Elden Ring. La compatibilità si decide dai file
> reali; una versione vecchia non diventa 1.17.1 copiando il manifesto.

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
2. Su Windows, scarica `ERITA-v0.9.7-Windows.zip` ed estrai l'intero ZIP in una
   cartella nuova e vuota, senza riusare la cartella di una versione
   precedente. Su Linux x86_64 o Steam Deck in modalità desktop, scarica
   `ERITA-v0.9.7-Linux-x86_64.tar.gz` ed estrai tutto l'archivio in un'altra
   cartella nuova e vuota, su un'unità `ext4`. (ERITA non ha ancora una
   release pubblicata: il pacchetto audio italiano è in lavorazione.)
3. Apri `ERITA.cmd` su Windows o `ERITA.sh` su Linux e clicca su **Correggi
   audio (ripristina)** se esiste un backup transazionale valido delle
   versioni 0.9.x sullo stesso sistema.
4. Se quel backup non esiste o il ripristino fallisce, su Steam apri **Libreria
   > Elden Ring > Proprietà > File installati > Verifica integrità dei file**.
5. Avvia il gioco una volta e conferma che l'audio originale funziona.
6. Apri di nuovo il launcher del tuo sistema e clicca su **Installa
   doppiaggio**.

Solo dopo aver confermato il recupero, rimuovi i file aggiuntivi che terminano
in `.bdt.original` dentro `ELDEN RING\Game\sd` e i `*.bk2.original` in
`ELDEN RING\Game\movie`/`movie_dlc`. Steam può conservare i file aggiuntivi
durante la verifica.

Il patcher attuale blocca l'installazione finché trova un `.original` legacy.
Preserva il file e non tenta mai di indovinare se appartiene al build attuale.

Non creare un'eccezione in Defender, non ripristinare manualmente un vecchio
backup e non eseguire il patcher come amministratore, con `sudo` o come root.
Usa lo stesso account del sistema per installare e ripristinare. Prima di
spostare o rinominare la libreria Steam, ripristina l'audio originale; se è già
stata spostata con il doppiaggio applicato, verifica l'integrità tramite
Steam.

Il pacchetto 0.9.7 installa audio WEM/BNK. Non copiarci le vecchie cartelle
`movie` o `movie_dlc`: il pacchetto opzionale di cutscene non ha ancora un
manifesto crittografico pubblico e verrà rifiutato.

## Note per Linux

Il pacchetto Linux include CPython 3.13.15 portatile e dipendenze offline: non
installare Python e non avviare il launcher con `sudo`. Cerca Steam nativo,
Flatpak e Snap, oltre alle librerie registrate in `libraryfolders.vdf`.

I backup non vanno copiati a mano tra Windows e Linux. Il supporto Linux della
0.9.7 è iniziale, limitato a x86_64 e `ext4`; NTFS, exFAT, btrfs e l'online su
Linux/Proton richiedono ancora test specifici prima di essere garantiti.
