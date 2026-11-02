# Nota di sessione — 30-31 ottobre 2026: la prima prova nel gioco

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la procedura sta in `doppiaggio/docs/WORKFLOW_CONSEGNE.md`.
> Segue `NOTE_SESSIONE_2026-10-30_note-per-tipo.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al
> 31 ottobre 2026".

## In breve

- **La guida del filmato arriva su Drive dal ponte.** `Ponte.gs` accetta
  `GUIDA_FILMATI_DOPPIATORI.pdf` in cima al pacchetto del filmato, e `lavora pubblica` la
  porta da `docs/` quando cambia. Il vecchio `copione.html` va tolto a mano: il ponte non
  cancella.
- **Ricevute le 2 consegne nuove del ponte** (Irina & Hyetta, solo note di prova; Margit, la
  riga 1).
- **Prima prova nel gioco:** 1.253 battute installate e verificate. Melina faceva un attimo
  d'inglese e poi silenzio. **Causa:** 29 battute hanno un pezzo iniziale (prefetch) in un
  soundbank; il gioco lo suonava e poi proseguiva dal `.wem` italiano come se fosse lo
  stesso audio. **Corretto:** `componi` scrive i 4 bank coinvolti cambiando solo il tipo di
  lettura di quei suoni, come fa il PT-BR. Provato nel gioco: Melina si sente intera.
- **Il volume** delle battute italiane è da 3 a 23 dB sotto l'inglese. L'utente ha deciso
  che lo farà la direzione, più avanti: l'allineamento automatico provato è stato tolto.
- **Il gioco è di nuovo originale** (Ripristina, controllato con `verifica`).

## 1. Il prefetch nei soundbank

- In Wwise un suono "PrefetchStreaming" ha i primi istanti dentro il bank, per partire
  subito, e il resto nel `.wem` sciolto. Sostituendo solo il `.wem`, il gioco suona il pezzo
  inglese e poi non riesce a decodificare il seguito: si sente un attimo d'inglese e silenzio.
- La correzione è il tipo di lettura del suono, da 1 (PrefetchStreaming) a 2 (Streaming): il
  gioco legge tutto dal `.wem`. ERITA lo sa già fare: unisce il bank del payload all'originale
  e accetta solo quel byte, e solo per i `.wem` del piano (`patcher/bnk.py`).
- `componi` (`soundbank_dei_prefetch` in `tools/lavora.py`) prende i bank dall'originale
  verificato, cambia quel byte per le nostre battute e controlla che l'unione di ERITA ridia
  esattamente lo stesso file. `verifica` confronta i bank del gioco con quell'unione.
- Il piano diceva il contrario (prova di agosto sull'ID 742636436), ma quella prova aveva
  installati anche i bank del PT-BR. Corretto in `PIANO_GESTIONE_DOPPIAGGIO.md`.
- I bank del PT-BR danno nel gioco gli stessi byte dei nostri, ma due (`cs_c4750`, `cs_m41`)
  hanno 9 suoni portoghesi incorporati, e coprono solo le battute che il PT-BR ha doppiato:
  non si usano.

## 2. Le prove

- **Prova mista**, voluta dall'utente: copia della `patch_data` del PT-BR 0.9.7 con sopra le
  nostre 1.253. I 136 bank in radice, doppioni di quelli in `enus/`, sono stati tolti per
  stare nei 9.240 file ammessi. Melina intera.
- **Prova da zero**, solo italiano coi 4 bank nostri: Melina intera.
- Le 94 battute troppo lunghe non entrano: nel gioco restano inglesi (lette dagli archivi).

## 3. Da sapere

- **ERITA per le prove la lancia l'utente** (`lavora.cmd prova` dal suo terminale): se la
  lancia Claude, il backup finisce nella cartella privata dell'app Claude, e Ripristina
  dell'utente non lo trova.
- `verifica` lanciata da Claude dice "modificato da qualcosa che non riconosco" dopo
  un'installazione dell'utente: è un falso allarme, per lo stesso motivo.

## 4. Commit

- `doppiaggio/`: `7dba8da` (guida del filmato), `717ae33`, `6347e63` (bank col prefetch),
  `643eb94`, `3165901` e la ripartenza di oggi. Non pushati.
- ERITA: questa nota. Non pushata.

## 5. Cosa resta

Nella §7 di `RIPARTIRE_DA_QUI.md`: ascoltare gli altri personaggi nel gioco, il volume (alla
direzione), togliere `copione.html` dal filmato su Drive, e il resto delle consegne.
