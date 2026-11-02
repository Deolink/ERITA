# Nota di sessione — 2 novembre 2026: una consegna per personaggio

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: il piano sta in `doppiaggio/docs/PIANO_CONSEGNA_UNICA.md`.
> Segue `NOTE_SESSIONE_2026-10-31_prima-prova-nel-gioco.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al
> 2 novembre 2026".

## In breve

- **Il problema:** nello strumento del controllo le consegne si accumulavano, una riga per
  ogni "Invia la consegna". Chi consegna a pezzi, o rimanda senza novità, lasciava più righe
  per lo stesso lavoro.
- **La causa:** ogni invio scrive sul ponte un elenco di tutto quello che il doppiatore ha
  in `audio-ita/` sul suo computer, anche se non è cambiato niente, e strumento e postazione
  ne facevano uno zip ciascuno. L'ultimo elenco può anche essere parziale (un altro
  computer, file tolti dopo l'invio).
- **La soluzione:** la consegna di un personaggio è l'unione dei suoi invii, e per ogni
  battuta vale la registrazione più recente. Una riga per personaggio nello strumento del
  socio, uno zip per personaggio nella postazione.
- **Pubblicati:** strumento del socio (versione 14), `Ponte.gs` (dall'utente, prova di
  sicurezza passata), le pagine dei 76 pacchetti.

## 1. Come funziona l'unione

- `ponte_client.leggi_elenchi`: gli elenchi di un personaggio, in cache per md5 (un elenco su
  Drive non cambia).
- `ponte_client.unione`: in ordine di data, per ogni file l'md5 dell'elenco più recente che
  lo contiene. Una presa che è poi diventata quella scelta non resta tra le prese.
- `ponte_client.ricostruisci_unione`: lo zip col nome dell'ultimo invio, con `consegne.json`
  (invii, origine di ogni file, file saltati). Un file che su Drive non corrisponde a nessun
  elenco (invio interrotto) e non è in cache resta fuori, con un avviso.
- Lo zip cambia nome a ogni invio nuovo e quelli di prima restano: l'esito del controllo,
  legato al nome dello zip, continua a dire se vale per la registrazione di oggi.
- Costo: l'unione di 100 invii da 200 battute è 3 ms; leggere i 100 elenchi dalla cache 23 ms.

## 2. Cosa è cambiato

- **Strumento del socio** (`tools/socio/controllo.py`):
  - una riga per personaggio (`per_personaggio`), con lo storico degli invii e "da controllare";
  - il report unico, col filtro "dall'ultimo invio";
  - "chi" ricavato togliendo il personaggio dal nome dello zip (`chi_dello_zip`);
  - la durata dell'originale presa dai campioni del wav inglese (`durata_originale`).
- **Postazione** (`tools/lavora.py`): `scarica_dal_ponte` per personaggio; `archivia` non rifà
  gli elenchi delle consegne arrivate dal ponte, che altrimenti sovrascriverebbe.
- **Ponte** (`Ponte.gs`, `consegna`): un elenco uguale all'ultimo non si scrive, e la
  risposta ha `uguale: true`. La pagina del pacchetto lo dice al doppiatore.
- **Guide:** doppiatori, socio e pannello.
- **In parallelo, un'altra sessione** ha corretto le durate nella pagina dei pacchetti: le
  registrazioni con esattamente i campioni dell'originale risultavano troppo lunghe
  (`misure.MARGINE_SOTTO` 0,001, `durata_originale` in `make_packet.py`). Lo stesso
  confronto nello strumento del socio l'ho corretto qui.

## 3. Prove

- Contro un finto ponte locale (`finto_ponte.py` nello scratchpad della sessione):
  - unione, 18 prove: a pezzi, reinvio uguale, rifatta, invio interrotto, elenco
    archiviato, presa scelta, zip vecchio con lo stesso nome;
  - strumento del socio, 17 prove, più pagina e report guardati nel browser;
  - postazione, 5 prove.
- `Ponte.gs` nel browser con Drive finto: quattro invii, i due uguali (anche in ordine
  diverso) non scrivono un elenco.
- Prova di sicurezza sul ponte vero dopo la pubblicazione: tutto rifiutato come doveva.
- **Non provato:** il caso "uguale" sul ponte vero, che servirebbe una consegna vera.

## 4. Cosa resta

Nella §7 di `RIPARTIRE_DA_QUI.md`: le misure tenute per md5, tenere solo l'ultimo zip
dell'unione, il caso "uguale" da guardare alla prima consegna ripetuta. Niente è
committato: lo decide l'utente, perché `make_packet.py` e `misure.py` contengono anche il
lavoro dell'altra sessione.
