# Nota di sessione — dal 4 al 12 novembre 2026: le battute fuori copione le decide il socio

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: i piani, con le scelte e le prove, stanno in
> `doppiaggio/docs/`. Segue `NOTE_SESSIONE_2026-11-03_socio-e-durate.md`.
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "Dove siamo
> (al 12 novembre 2026)".

## In breve

- **4-10 novembre**, in più sessioni (i piani dicono il dettaglio):
  - le note non si perdono più: il ponte unisce le note del doppiatore invece di
    sostituirle (`PIANO_NOTE_SENZA_PERDITE.md`);
  - nel report del socio il filtro per tipo di nota e il caricamento visibile
    (`PIANO_INTERFACCIA_CARICAMENTI.md`);
  - le note in anticipo: il report anche per i personaggi senza consegne
    (`PIANO_NOTE_IN_ANTICIPO.md`);
  - i copioni: le battute che hanno ritrovato il sottotitolo, i testi simili, il narratore
    con i suoi sottotitoli ufficiali, e le battute tolte dal gioco ma doppiate dal brasiliano
    messe nel copione come *facoltative* (`PIANO_COPIONI_RITROVATE.md`);
  - il copione del socio (`durate.csv`) arriva con l'aggiornamento firmato dal ponte;
  - `tools/controlla_allineamento.py`: copioni, strumento del socio, elenchi e Drive dicono
    la stessa cosa?
- **11-12 novembre: lo strumento del socio 22 e 23.** Le battute fuori copione le decide il
  socio, nel report, una per una (`PIANO_REVISIONE_SOCIO.md`, §2, §2bis, §2ter).
- **Il foglio dell'avanzamento** ha il tipo della battuta e due stati nuovi. Un errore nella
  scrittura, trovato con le consegne vere e corretto lo stesso giorno.
- **Pubblicati il 12 novembre:** `Ponte.gs` (due volte, dall'utente) e lo strumento del
  socio 22 e poi 23. Tutto in linea su Drive.

## 1. Le battute fuori copione

Il copione ha 10.064 righe. 9.035 sono battute del gioco; 1.029 sono fuori copione:

| tipo | quante | cos'è |
|---|--:|---|
| facoltativa | 366 | tolta dal gioco, doppiata dal brasiliano; il testo è una traduzione nostra |
| tagliata | 81 | tolta dal gioco, senza testo: l'inglese è una trascrizione della community |
| verso | 582 | versi e sforzi, senza testo (362 nel solo pacchetto dei versi) |

Se farle lo decide il socio. Com'è fatto nello strumento:

- **Nel report**, sotto ogni battuta fuori copione: *da fare*, *non fare*, *non so*, e per
  facoltative e tagliate il testo italiano da correggere sul posto.
- **I versi uno per uno**, con l'etichetta *verso*. In cima al report c'è la scelta per
  tutti i versi del personaggio, che vale per quelli senza la loro.
- **Il report di una consegna ha tutte le battute del personaggio**: anche quelle del
  copione non consegnate (*manca*: testo, inglese e note, senza approvazione) e quelle da
  decidere. Una nota scritta su una battuta non consegnata arriva al doppiatore, ma non
  segnala niente.
- **Gli stati:** *da decidere* (tocca al socio) e *non si fa*. "Tagliata" era anche uno
  stato: ora è solo un tipo, perché indicava due cose diverse e somigliava a "da tagliare".
- **Una battuta già consegnata resta**, anche se poi viene decisa "non fare": conta come le
  altre e la postazione la mette nel gioco.
- **Nella pagina principale:** la colonna *da decidere* nella tabella delle consegne (un
  clic apre il report già filtrato), e in fondo la tabella *Da non considerare* con le non
  consegnate decise "non fare" e il nome del file che avrebbero.
- **Le decisioni** stanno su Drive in un file del socio, scritto dal ponte con due
  operazioni nuove (leggere: socio e postazione; scrivere: solo il socio). Vince la più
  recente, così due persone non si cancellano.

## 2. Il foglio dell'avanzamento

- Scheda Battute: colonna **tipo**, stati *da decidere* e *non si fa*. Riepilogo: colonne
  *da decidere* e *non si fanno*. Da fare: anche le righe del socio. Info: la legenda.
- In `Ponte.gs` le colonne si cercano per intestazione, non più per posto.
- **L'errore del 12 novembre.** Con le colonne nuove la scrittura falliva: lo strumento del
  socio diceva solo "errore interno", e il dettaglio, che il ponte dà alla sola postazione,
  era "Queste colonne sono fuori dai limiti". Prima di riscrivere una scheda il ponte
  rileggeva i criteri del filtro di prima anche per le colonne nuove, che quel filtro non
  aveva. Ora la scheda si allarga se serve, e i criteri si tengono solo quando le colonne non
  sono cambiate.
- **Perché le prove non l'avevano visto:** il foglio finto rispondeva a qualunque colonna.
  La prova nuova usa fogli finti con la forma di prima e un filtro che rifiuta le colonne che
  non ha; lo script di prima ci fallisce con lo stesso messaggio del foglio vero.
- **Da ricordare:** quando cambiano le colonne di una scheda, dopo aver reincollato
  `Ponte.gs` va rilanciata `impostaAvanzamento()`.

## 3. Altre cose trovate provando con le consegne vere

- **I report sono pagine già scritte.** Dopo l'aggiornamento dello strumento restavano
  quelle della versione di prima, senza le novità, finché non si premeva "Controlla le
  consegne": sembrava che le battute da decidere mancassero. Ora la pagina principale lo
  dice con un avviso.
- **Il salvataggio del nome** di chi usa lo strumento non aveva un blocco: due richieste
  insieme potevano fallire su Windows senza salvare. Corretto.
- **La prova di sicurezza del ponte** cercava le celle del foglio per posto: con la colonna
  nuova dava un falso allarme. Ora le cerca per contenuto.
- **Un controllo completo dura quasi sei minuti** anche senza consegne nuove: rifare i 19
  report costa meno di due secondi, il resto è il dialogo col ponte.

## 4. Lo stato al 12 novembre

- **Sul ponte:** 33 invii di 16 personaggi. Delle loro 3.109 righe: 1.975 consegnate (1.178
  ok, 100 segnalate, 697 da controllare), 831 che mancano, 303 da decidere. Nessuna
  decisione ancora presa.
- **Sulla postazione:** ferma al 3 novembre, con 12 personaggi e `patch_data` di 1.445
  battute. Sono da ricevere 7 personaggi con invii nuovi.
- **Prove:** lo script del ponte con Node su fogli finti (27 controlli sulla forma nuova, 48
  su quella di prima); lo strumento sul banco finto (43 controlli) e nel browser; la prova di
  sicurezza sul ponte vero (63 casi rifiutati come dovevano).
- **In git:** tutto committato nei due repo. In `doppiaggio/` una quarantina di commit non
  sono ancora su GitHub.

## 5. Cosa resta

Nei lavori aperti della §7 di `RIPARTIRE_DA_QUI.md`. In particolare:

- **le decisioni del socio non tornano ancora nei copioni dei doppiatori:** la postazione
  non legge il file delle decisioni (§3 di `PIANO_REVISIONE_SOCIO.md`);
- ricevere le consegne sulla postazione;
- mandare gli avvisi, pronti dal 10 novembre;
- guardare il foglio con le colonne nuove e condividerlo;
- per due personaggi gli esiti del controllo sul ponte non coincidono con quelli dello
  strumento in postazione: da capire.
