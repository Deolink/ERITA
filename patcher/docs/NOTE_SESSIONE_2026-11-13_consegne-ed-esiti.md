# Nota di sessione — 13 novembre 2026: le consegne ricevute, gli esiti tra copie dello strumento

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento. Segue `NOTE_SESSIONE_2026-11-12_fuori-copione.md`, che arriva
> fino alla mattina del 13 novembre (le decisioni nei copioni).
>
> Il punto da cui ripartire è la §2 di `doppiaggio/docs/RIPARTIRE_DA_QUI.md`, "Dove siamo
> (al 13 novembre 2026)".

## In breve

- **La postazione ha ricevuto le consegne**, ferma dal 3 novembre: ora ha 16 personaggi e
  `patch_data` ha 1.850 battute (erano 1.445).
- **Kalé e Roderika:** capito perché gli esiti del controllo su Drive non coincidevano con
  quelli dello strumento in postazione. Roderika era giusta. Per Kalé era un limite dello
  strumento del socio, corretto e pubblicato lo stesso giorno.
- **Trovato e non corretto:** i WAV a 32 bit float di Kenneth Haight, che il controllo della
  postazione dà "illeggibili" anche se entrano nel gioco.

## 1. Le consegne ricevute

`lavora nuove`, su richiesta dell'utente: scarica dal ponte, riceve, controlla, codifica,
ricompone `patch_data`.

| personaggio | registrazioni | in `patch_data` | entrate sotto la qualità 4 |
|---|--:|--:|---|
| Kalé (nuovo) | 191 | 191 | 146, 175, 185, 308 |
| Ranni the Witch (nuovo) | 105 | 105 | – |
| Kenneth Haight (nuovo) | 29 | 29 | – |
| Iron-Fist Alexander (nuovo) | 16 | 16 | 3 |
| Margit or Morgott | 57 | 57 | 4 |
| Bernahl, the Recusant | 102 | 102 | – |
| Roderika | 171 | 171 | 1, 38, 40, 45, 60, 67 |

- **In tutto:** 16 personaggi, 1.975 registrazioni in 27 zip, 1.850 battute in `patch_data`
  e 9 soundbank col prefetch.
- **Fuori 106 battute**, tutte dei personaggi di prima: 95 troppo lunghe, 8 più lunghe di
  pochi millesimi, 3 che sforano lo slot. Bernahl, con le 17 rifatte, è tutto dentro.
- **Da tagliare 35, da riregistrare 75** (`lavora taglia --prova`): erano 40 e 78.
- **Prese in più:** 63 di Margit e 1 di Kalé, da parte finché nessuno le sceglie.
- Il gioco non è stato toccato: nessuna installazione, nessuna prova nel gioco.

## 2. Kenneth Haight: i WAV a 32 bit float

- Le sue 29 registrazioni sono WAV in virgola mobile a 32 bit (formato 3), non PCM.
- `tools/verifica_consegne.py` legge solo il PCM: le dà tutte "illeggibili", e così il report
  della consegna e la colonna "da rifare" di `lavora stato`.
- **È un falso allarme:** Wwise le codifica, le durate tornano contro l'originale e sono
  tutte e 29 in `patch_data`.
- Quello che manca davvero è la misura sulla registrazione (durata, silenzi, rumore).
- **Non guardato:** cosa ne dicono lo strumento del socio e il copione del doppiatore.
- Due strade, da decidere: far leggere il float al controllo, o chiedere di esportare in PCM
  a 24 bit.

## 3. Kalé e Roderika: gli esiti tra ponte e strumento

Confronto tra `note/controllo.json` su Drive (com'era il 12 novembre) e quello che lo
strumento considera valido, per tutti e 16 i personaggi: differivano solo questi due.

- **Roderika era giusta.** Su Drive c'erano 6 segnalazioni del 2 novembre; l'8 novembre
  quelle 6 battute sono state rifatte, e lo strumento le dà "da controllare" perché la
  registrazione è cambiata. Le altre 165 non hanno mai avuto un esito.
- **Kalé no.** Il socio aveva dato 191 ok: 167 quando l'ultimo invio era quello del 7
  novembre, 24 sulle rifatte dell'8.
  - Ogni esito porta il nome dello zip ascoltato, che è il nome dell'ultimo invio di quel
    momento.
  - Lo strumento considerava valido un esito solo se aveva quello zip in locale.
  - La copia in postazione aveva scaricato Kalé il 6 e il 10 novembre: lo zip del 7 non
    l'ha mai avuto, e dava "da controllare" 167 battute che il socio aveva approvato.
  - Le registrazioni erano le stesse: nell'unione di oggi vengono tutte da invii del 6 e
    del 7 novembre.

**Cosa comportava:**

- I numeri del 12 novembre (1.178 ok, 697 da controllare) erano contati dalla copia in
  postazione. Con la correzione sono **1.345 ok e 530 da controllare**.
- Il foglio dell'avanzamento diceva l'una o l'altra cosa secondo la copia che lo scriveva
  per ultima.
- **Il rischio più serio:** quando una copia manda le note del controllo, il ponte
  sostituisce il file intero, e la copia toglie prima gli esiti che per lei non valgono. Una
  nota su Kalé scritta dalla copia in postazione avrebbe tolto da Drive i 167 ok del socio.
- Vale per qualunque copia che salta un invio intermedio di un personaggio.

## 4. La correzione

In `doppiaggio/tools/socio/controllo.py`:

- `stessa_registrazione`, usata da `esito_valido` e da `vale_per`. Se lo zip ascoltato c'è,
  confronta i due file come prima. Se non c'è, guarda l'unione di oggi: l'esito vale se
  l'invio che ha portato la registrazione non viene dopo quello dello zip ascoltato.
- `origini`, che legge dallo zip dell'unione (`consegne.json`) da quale invio viene ogni
  registrazione.
- Con uno zip di prima, senza unione, o una consegna che l'unione non conosce, l'esito non
  vale, come prima.
- `VERSIONE` resta 23: la pagina del report non cambia, e alzarla farebbe rifare tutti i
  report e comparire l'avviso al socio senza motivo.
- Non cambiano il ponte, i pacchetti né il formato delle note.

**Prove**, sul banco finto (`prove-ponte/interfaccia`, `prove22/prova_esiti.py`, 33
controlli):

- Albus del banco, che ha due invii e solo lo zip del secondo, come Kalé: 17 ok e 17 da
  controllare, nell'avanzamento e nella tabella delle consegne. Con lo strumento di prima,
  sullo stesso caso: 0 ok e 34 da controllare.
- Quattro invii con battute rifatte prima e dopo l'ascolto: la copia senza gli zip di mezzo
  dice le stesse cose di quella che li ha tutti, in tutti e 16 i casi.
- Quello che parte per Drive: gli ok dell'altra copia restano, quello su una battuta rifatta
  se ne va.
- Un nome con l'accento scritto nei due modi, uno zip senza unione, una consegna sconosciuta.
- Le prove di prima (`prova_strumento.py`) passano.
- Sulle consegne vere, **solo contando, in sola lettura**: Kalé 191 ok, Roderika 171 da
  controllare.

**Non provato:** nel browser, e nello strumento vero dopo l'aggiornamento.

**Pubblicata** su richiesta dell'utente: `controlla_allineamento.py --drive` prima (una sola
differenza, `controllo.py`), `lavora pubblica --socio --prova`, poi `lavora pubblica --socio`
(un file caricato, `versione.json` firmato) e l'allineamento dopo, tutto in linea.

## 5. Cosa resta

Nei lavori aperti della §7 di `RIPARTIRE_DA_QUI.md`. In particolare:

- riavviare lo strumento con le consegne vere in postazione, che così si aggiorna, e
  guardare che Kalé abbia 191 ok. **Fino ad allora, da quella copia niente note né esiti su
  Kalé**;
- mandare gli avvisi, pronti dal 10 novembre;
- guardare il foglio con le colonne nuove e condividerlo;
- il push dei due repository, dal terminale dell'utente;
- Kenneth Haight e i WAV a 32 bit float (§2);
- la nota delle 34 facoltative, che il socio non vede quando decide;
- un `desktop.ini` in `pacchetti/Irina_Hyetta/audio-ita/`, che il controllo segnala a ogni
  giro come nome sbagliato.
