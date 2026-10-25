# Nota di sessione — 25 ottobre 2026, pomeriggio: la coda dei tagli

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la regola stabile sta in
> `doppiaggio/docs/WORKFLOW_CONSEGNE.md`, "Il report delle battute da rifare" e "Togliere il
> silenzio: `taglia`". Segue `NOTE_SESSIONE_2026-10-24_drive-consegne.md` e ne corregge le §5 e §6.
>
> **Pushato il 25 ottobre sera.** Il punto da cui ripartire è la §2 di
> `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "In breve, al 25 ottobre 2026, sera" (repo privato
> del doppiaggio, dove ci sono anche gli elenchi per doppiatore).

## In breve

Ascoltando le battute tagliate, alcune avevano **la fine troncata**. La causa era la soglia
del silenzio: tutto quello sotto -45 dBFS contava come silenzio, ma dopo l'ultima parola
restano spesso decimi di secondo tra -45 e -60 dBFS (la parola che si spegne, un respiro, la
stanza). Il taglio cadeva lì in mezzo.

Ora **la coda finisce sotto -60 dBFS**, o 10 dB sopra il rumore di fondo se il fondo è alto, e
dopo restano 100 ms. Se così la battuta non rientra nella durata dell'originale, **va
riregistrata**: meglio rifarla che troncarla. I tagli sono stati rifatti con la regola
nuova.

| | prima | dopo |
|---|---|---|
| tagli in `manifest/tagli.csv` | 185 | 138 |
| secondi tolti in coda / in testa | 57 / 9 | 22 / 15 |
| battute in `patch_data` | 938 | 897 |
| da riregistrare | 18 | 65 |

Nel gioco non c'era niente installato (vedi sotto), quindi niente da togliere lì.

## 1. Cosa si è visto

Prima di cambiare la regola sono state misurate, per tutti i 185 tagli, il livello del suono
nel punto in cui il file finisce e quanto suono c'è ancora dopo:
- 29 tagli chiudevano il file sopra -50 dBFS, 59 sopra -55 dBFS, 102 sopra -60 dBFS;
- nelle code tipiche, dopo la voce: 0,2–0,4 s tra -47 e -55 dBFS, poi la discesa sotto -60.

Il confronto con gli originali inglesi (gli WAV di riferimento nei pacchetti) ha dato anche
un altro dato: gli inglesi partono quasi subito (mediana del silenzio in testa 0,02 s, contro
0,13 s delle registrazioni italiane) e hanno più coda (0,55 s contro 0,38 s). Lo spazio da
recuperare, quando c'è, sta più in testa che in coda.

## 2. I passaggi, e un primo tentativo sbagliato

1. **Primo tentativo: 100 ms di coda invece di 50, il resto dalla testa.** Non bastava: il
   problema era la soglia, non il margine. Ha però fatto emergere due difetti veri, corretti
   e rimasti:
   - **La griglia di misura.** Il silenzio si misura a blocchi da 10 ms dall'inizio del
     file. Togliendo in testa un numero di campioni non multiplo del blocco, la griglia si
     sposta di qualche millesimo e una dissolvenza appena sotto soglia può tornare "voce":
     il controllo finale rimisurava e scartava il taglio. Ora `tagli.allinea()` arrotonda per
     eccesso i tagli a blocchi interi (meno di 10 ms in più per lato).
   - **`taglia --prova` non faceva il controllo finale**, e prometteva tagli che poi venivano
     saltati. Ora lo fa in memoria, con `tagli.controlla()`, la stessa funzione del taglio
     vero.
2. **La regola nuova** (scelta tra -55 e -60 dBFS; scelto -60 perché si preferisce
   riregistrare). Simulata prima su tutti i 185 tagli: 47 sarebbero diventati da
   riregistrare (con -55 sarebbero stati 38).
3. **Rifatti i tagli:** `taglia --annulla` sui 115 tagli che toglievano dalla coda più di
   quanto ammette la regola nuova (originali rimessi, verificati per SHA-256 contro il
   registro), poi `taglia` su tutto: 68 battute ritagliate (42 testa e coda, 26 solo testa),
   nessuna scartata dal controllo.
4. **Lo strumento del socio** è stato rigenerato con la regola nuova (`lavora socio`).

## 3. Cosa è cambiato in `doppiaggio/`

- `tools/misure.py`: la coda si misura con `SOGLIA_CODA_DB = -60` (o fondo +
  `SOPRA_FONDO_CODA_DB`, mai sopra la soglia della testa); `MARGINE_CODA = 0.10`. La testa
  resta a -45 dBFS con 50 ms di margine.
- `tools/tagli.py`: `allinea()` e `controlla()`; il controllo vuole almeno 80 ms in coda e
  30 ms in testa.
- `tools/lavora.py`: `taglia` allinea i tagli e fa il controllo anche con `--prova`.
- `tools/report_consegne.py`: i messaggi citano i margini nuovi.
- `docs/WORKFLOW_CONSEGNE.md`: le regole del calcolo e di `taglia`.
- `manifest/tagli.csv`: 138 tagli.

## 4. Da sapere

- **I tagli rimasti con la regola vecchia** (70) sono quelli che già rispettavano la nuova:
  non sono stati toccati.
- **5 tagli lasciano 94–95 ms invece di 100**: è l'arrotondamento ai blocchi da 10 ms, e
  dopo il punto a -60 dBFS è comunque silenzio.
- **24 battute ora sono tagliate solo in testa**, perché in coda non c'era niente da
  togliere: la voce parte un po' prima, vanno ascoltate. La testa usa ancora -45 dBFS.
- **Una misura fragile, non corretta:** l'ultimo blocco di un file, se più corto di 10 ms,
  può risultare "voce" per pochi campioni rumorosi. Con la griglia allineata non ha dato
  problemi, ma resta da tenere presente.
- **Qualità della codifica**, per riferimento: si parte da Vorbis 7 (mono) e 4 (stereo) e si
  scende di un gradino alla volta, fino a 0, solo per le battute che non entrano nello slot.
  Sotto 4 la battuta è "da ascoltare". Sulle 977 registrazioni: 21 entrate solo sotto 4, 2
  che non entrano nemmeno a 0.

## 5. Stato della giornata, fuori dai tagli

- `git fetch upstream`: nessuna versione dopo la 0.9.7.
- `verifica`: **nel gioco nessun doppiaggio installato**, archivi originali; anche le 101
  battute della prima consegna non ci sono più (è stato fatto *Ripristina*).
- Su Drive è arrivata **una consegna nuova**, non ancora scaricata.
- In `doppiaggio/` c'erano anche modifiche agli strumenti fatte alle 14:22 e mai committate
  (avanzamento di download e controlli, nuovi tentativi della pagina, una porta sola per il
  pannello): ora sono in un commit loro. Lo zip del socio le contiene.

## 6. Per continuare

1. Ricevere la consegna nuova.
2. Far riregistrare le 65 battute: elenco per doppiatore in
   `doppiaggio/docs/RIPARTIRE_DA_QUI.md` (§7, voce 8).
3. Installare le 897 battute nel gioco e ascoltarle, a partire da quelle tagliate in testa.
4. Pulizia facoltativa in `doppiaggio/distribuzione/`: le cartelle
   `ERITA-Controllo.nuova-*`.
