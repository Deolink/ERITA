## ERITA 0.9.7 — Linux, Steam Deck e mitigazione per Sellen

> Nota per ERITA: il codice di questa versione è allineato alla 0.9.7 del
> progetto originale ERPT-BR. I valori del payload e i test descritti qui sotto
> si riferiscono al pacchetto audio PT-BR dell'upstream; il pacchetto audio
> italiano è ancora in lavorazione e avrà valori propri.

Questa versione aggiunge un pacchetto portatile per **Linux x86_64** e **Steam
Deck in modalità desktop** e applica una mitigazione prudente al bug segnalato
nella sequenza della Pietra Brillante Primordiale di Sellen.

### Download

- Windows x64: **`ERITA-v0.9.7-Windows.zip`**;
- Linux x86_64/Steam Deck: **`ERITA-v0.9.7-Linux-x86_64.tar.gz`**.

Non usare gli archivi automatici **Source code** di GitHub: non contengono il
runtime, le dipendenze e il payload completi.

> [!IMPORTANT]
> Su Windows e su Linux, estrai la 0.9.7 in una **cartella nuova e vuota**. Non
> estrarla sopra una versione precedente: il WEM rimosso potrebbe restare come
> avanzo e l'installer rifiuterebbe giustamente l'albero incompleto.

### Cosa è cambiato

- nuovo launcher trasparente `ERITA.sh` per Linux x86_64;
- rilevamento di Steam nativo, Flatpak e Snap;
- lettura delle librerie aggiuntive registrate in `libraryfolders.vdf`;
- runtime portatile Astral `python-build-standalone` 20260924 con CPython
  3.13.15 fissato e autenticato;
- wheel Linux bloccati per versione e SHA-256, installati localmente in
  modalità offline;
- primo avvio senza Python di sistema, `sudo`, root né accesso alla rete;
- l'effetto non verbale `553755359.wem`, che superava la durata originale
  durante l'animazione di Sellen, ora resta nell'audio vanilla;
- nessuna battuta doppiata di Sellen è stata rimossa.

### Installazione su Linux

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Estrai tutto il `tar.gz` in una cartella nuova e vuota su `ext4`; non
   estrarlo sopra una versione precedente.
3. Avvia `ERITA.sh` senza `sudo`.
4. Conferma la cartella `ELDEN RING/Game` rilevata oppure selezionala.
5. Installa il doppiaggio e apri il gioco normalmente dalla stessa Steam.

Su Steam Deck, fai la procedura in **modalità desktop**.

### Compatibilità e manifesto Steam

`appmanifest_1245620.acf` resta facoltativo. La sua assenza, una divergenza o
la presenza di una copia esterna non bloccano un profilo reale riconosciuto, e
chi ha già quel file può lasciarlo dov'è. Il manifesto inoltre non autorizza mai
file incompatibili.

I file audio reali di Elden Ring 1.17.1 restano l'autorità. I BHD, le
dimensioni dei BDT e il baseline completo devono corrispondere al profilo
omologato; una versione vecchia non diventa compatibile copiando un manifesto.

### Portata iniziale del supporto Linux

L'obiettivo di questa versione è Linux x86_64 su `ext4`, compreso Steam Deck in
modalità desktop. NTFS, exFAT e btrfs non hanno ancora garanzie di
compatibilità senza test specifici.

Il payload di base ha già avuto una sessione online riuscita su Windows. La
mitigazione di Sellen riporta un solo effetto al vanilla, ma deve ancora essere
confermata nella missione. Il test precedente non prova nemmeno il nuovo
ambiente Linux/Proton. Il pacchetto Linux deve completare la convalida in CI e
un test fisico riproducibile prima che il progetto prometta il funzionamento
online su quella piattaforma.

### Integrità dell'audio

Il payload ha 8.968 WEM e 272 alias BNK. Lo SHA-256 canonico dell'albero è:

`e97467e8ebbd1da87be96a44e4a2ee5694cd41c0bf592159b0570258d0b8460e`
