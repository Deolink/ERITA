## ERITA 0.9.6 — manifesto Steam facoltativo

> Nota per ERITA: questa è la traduzione delle note della versione 0.9.6 del
> progetto originale ERPT-BR, il cui codice è incluso in ERITA. Il payload
> descritto qui sotto è quello PT-BR dell'upstream; ERITA non ha ancora
> pubblicato un proprio pacchetto audio.

Questo hotfix corregge l'installazione su copie valide di Elden Ring 1.17.1 che
non hanno `appmanifest_1245620.acf` nella libreria rilevata.

### Cosa è cambiato

- la compatibilità ora si decide dai file audio reali del gioco;
- un manifesto assente, illeggibile, non collegato o con un altro BuildID non
  blocca quando viene riconosciuto il profilo reale 1.17.1;
- chi ha già copiato il manifesto distribuito altrove può lasciarlo dov'è e
  installare normalmente;
- il manifesto da solo non autorizza mai file incompatibili e non viene copiato,
  scaricato né incluso da ERITA;
- i file fuori dal profilo ricevono l'errore esplicito `ERITA-FILES-001`, prima
  di qualunque modifica;
- l'interfaccia non usa il manifesto per promettere che Steam o l'online siano
  confermati.

L'audio non è cambiato: la 0.9.6 riusa esattamente il payload corretto e
autenticato della 0.9.5, con 8.969 WEM e 272 alias BNK. Lo SHA-256 canonico
dell'albero resta
`8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb`.

### Download e installazione

Scarica solo **`ERITA-v0.9.6-Windows.zip`**, estrai tutto il contenuto e fai
doppio clic su **`ERITA.cmd`**. Non usare gli ZIP automatici **Source code** di
GitHub e non serve scaricare nessuno ZIP di manifesto.

Il pacchetto resta senza un eseguibile proprio del progetto, senza Mod Engine 3
e senza disattivare l'Easy Anti-Cheat. Apri il gioco normalmente tramite Steam
e conferma che Steam riconosca e aggiorni l'installazione prima di giocare
online.

### Limite di questa versione

L'hotfix toglie la dipendenza dal manifesto, ma non trasforma file vecchi in
1.17.1. I BHD, le dimensioni dei BDT e il baseline completo devono
corrispondere al profilo omologato. Una versione reale diversa ha ancora
bisogno di un profilo e di un adattamento propri; copiare un manifesto non
cambia i file del gioco.
