# Incidente audio nelle versioni 0.9.1 e 0.9.2

## Stato

**Risolto nella versione 0.9.4** per Elden Ring 1.17.1 (Steam BuildID
`25080141`); la correzione è inclusa anche nel codice di ERITA 0.9.7. Le
versioni 0.8.4, 0.9.1 e 0.9.2 restano interessate e non vanno usate come
alternativa.

## Sintomo

Sono stati segnalati suoni mancanti nell'interfaccia, inclusi i clic del menu,
dopo l'installazione del doppiaggio.

## Cosa fare se è stata installata una versione interessata

1. Chiudi Elden Ring ed Easy Anti-Cheat.
2. Scarica ed estrai `ERITA-v0.9.7-Windows.zip`.
3. Apri `ERITA.cmd` e clicca su **Correggi audio (ripristina)**.
4. Se il backup non fosse disponibile o il ripristino fallisse, usa **Steam >
   Elden Ring > Proprietà > File installati > Verifica integrità dei file**.
5. Conferma l'audio originale e solo dopo usa **Installa doppiaggio** nella
   versione 0.9.7.

## Diagnostica tecnica

L'installazione controllata non ha avuto un errore casuale di copia: i 9.105
slot scritti coincidevano con il piano del patcher e i byte fuori da essi sono
rimasti identici al backup. Il problema stava nel contenuto vecchio:

- le versioni 0.9.1 e 0.9.2 riutilizzavano il payload `v0.8.1`;
- `enus/cs_main.bnk` rimuoveva tre media e 234 oggetti HIRC presenti nel banco
  originale di Elden Ring 1.17.1;
- `enus/cs_m41.bnk` rimuoveva altri cinque media;
- i BNK incompatibili spiegano la perdita di clic e suoni; le divergenze degli
  hash BHD, descritte sotto, sono un limite separato del metodo diretto.

## Correzione

Nella 0.9.4 i 136 banchi fisici sono stati ricostruiti usando i banchi
originali della versione 1.17.1 come autorità strutturale. Sono stati inseriti
solo oggetti e media del doppiaggio compatibili; gli eventi e i suoni attuali
del gioco sono stati preservati.

Il payload finale ha superato la convalida completa, due compressioni
deterministiche, installazione, reinstallazione, confronto dei byte fuori dagli
slot e ripristino. Chi ha eseguito il test reale per il progetto originale ha
confermato i suoni dei clic e una sessione online avviata normalmente da Steam
con Easy Anti-Cheat attivo.

La 0.9.4 corregge il contenuto dei BNK, ma non riscrive né rifirma gli indici
BHD. Per questo le 8.973 risorse modificate continuano a divergere dagli hash
salted originali. Il patcher accetta solo questo insieme esatto di divergenze,
legato al payload autenticato e al piano di installazione; qualunque
divergenza in più interrompe l'operazione. Il test online riuscito non elimina
questo limite.

Quel test documenta l'ambiente verificato, ma non è una garanzia di rischio
zero per versioni future del gioco, dell'EAC o delle regole del servizio.
