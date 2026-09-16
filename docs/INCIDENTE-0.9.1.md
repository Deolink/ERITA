# Incidente audio nelle versioni 0.9.1 e 0.9.2

## Stato

**Installazione sospesa.** Questo avviso riguarda le versioni 0.9.1 e 0.9.2 su
Elden Ring 1.17.1 (Steam BuildID 25080141). La versione 0.8.4 non è
un'alternativa sicura, perché usa lo stesso vecchio pacchetto audio.

## Sintomo

Sono stati segnalati suoni mancanti nell'interfaccia, inclusi i clic del menu,
dopo l'installazione del doppiaggio.

## Cosa fare ora

1. Non aprire la modalità online finché i file modificati sono installati.
2. Chiudi Elden Ring ed Easy Anti-Cheat.
3. Scarica/apri ERITA 0.9.3 e clicca su **Correggi audio (ripristina)**. Nelle
   versioni precedenti, lo stesso pulsante appare come **Ripristina originale**.
4. Se il backup non fosse disponibile o il ripristino fallisse, usa **Steam >
   Elden Ring > Proprietà > File installati > Verifica integrità dei file**.
5. Apri prima il gioco per confermare i clic e i suoni originali; solo dopo
   torna in modalità online.

## Diagnostica tecnica

L'installazione controllata non ha avuto un errore casuale di copia: i 9.105
slot scritti coincidono esattamente con il piano del patcher e i byte fuori da
essi restano identici al backup. Il problema sta nel contenuto e nel metodo:

- le versioni 0.9.1 e 0.9.2 riutilizzano il pacchetto `v0.8.1`, precedente
  all'attuale build;
- l'`enus/cs_main.bnk` di quel pacchetto rimuove tre media e 234 oggetti HIRC
  presenti nel banco originale di Elden Ring 1.17.1;
- l'`enus/cs_m41.bnk` rimuove altri cinque media;
- 8.976 risorse modificate non corrispondono più agli hash salted registrati
  negli indici BHD originali.

Il backup transazionale dell'installazione controllata è rimasto integro. La
correzione sarà costruita sui banchi originali della versione 1.17.1,
preservando i media e gli eventi aggiunti dal gioco. La release tornerà
installabile solo dopo test reali di clic del menu, battute, cutscene del
gioco base e del DLC, ripristino e sessione online con l'Easy Anti-Cheat.
