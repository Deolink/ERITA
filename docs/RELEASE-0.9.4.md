## ERITA 0.9.4 — installazione riattivata

> Nota per ERITA: questa è la traduzione delle note della versione 0.9.4 del
> progetto originale ERPT-BR, il cui codice è incluso in ERITA. Il payload
> descritto qui sotto è quello PT-BR dell'upstream; ERITA non ha ancora
> pubblicato un proprio pacchetto audio.

Questa versione corregge l'incidente audio delle versioni 0.9.1 e 0.9.2 e torna
a installare il doppiaggio su Elden Ring 1.17.1, Steam BuildID `25080141`.

### Download

Scarica solo **`ERITA-v0.9.4-Windows.zip`**, estrai tutto il contenuto e fai
doppio clic su `ERITA.cmd`. Non usare gli ZIP automatici **Source code** di
GitHub: non contengono il pacchetto completo.

### Correzioni e miglioramenti

- banchi Wwise ricostruiti sui banchi originali del gioco attuale;
- clic del menu, eventi e media introdotti dal gioco preservati;
- 8.969 WEM e 272 alias BNK autenticati, 9.241 file in totale;
- installazione, reinstallazione e ripristino transazionali verificati;
- installer con un clic in codice sorgente, senza un `.exe` proprio;
- rilevamento della cartella e del BuildID tramite Steam;
- diagnostica locale con errore esplicito e condivisione manuale.

Payload interno: 588.468.447 byte, SHA-256
`430e9693a9b3313826e9f7c890cf592eb5b468d145bb405e8a4586002b877680`.

### Online

La versione è stata testata in una sessione reale avviata normalmente da Steam,
con Easy Anti-Cheat e connessione online attivi. I suoni dei clic hanno
funzionato e il gioco è rimasto online durante il test. L'installer non
disattiva né modifica l'EAC.

Limite noto: il metodo modifica dati nei BDT senza riscrivere o rifirmare gli
indici BHD. Le 8.973 risorse modificate divergono dagli hash salted originali;
l'installer accetta solo le divergenze esatte del piano e del payload
autenticati e rifiuta qualunque altra. Il test online non elimina questo limite
tecnico.

Il risultato vale per la versione e la sessione testate; non è una garanzia di
rischio zero contro cambiamenti futuri del gioco, dell'EAC o delle regole del
servizio.

### Per chi ha installato una versione interessata

Usa prima **Correggi audio (ripristina)**. Se non c'è un backup valido, esegui
la verifica di integrità tramite Steam. Dopo aver confermato l'audio originale,
installa la 0.9.4.

Non usare la 0.8.4, la 0.9.1 o la 0.9.2 come alternativa.
