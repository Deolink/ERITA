## ERITA 0.9.5 — pacchetto piatto per Windows

> Nota per ERITA: il codice di questa versione è allineato alla 0.9.5 del
> progetto originale ERPT-BR. I valori del payload e il test online descritti
> qui sotto si riferiscono al pacchetto audio PT-BR dell'upstream; il pacchetto
> audio italiano è ancora in lavorazione e avrà valori propri.

Questa versione mantiene la correzione audio per Elden Ring 1.17.1, Steam
BuildID `25080141`, e cambia la struttura del download per ridurre i falsi
positivi degli scanner automatici.

### Download

Scarica solo **`ERITA-v0.9.5-Windows.zip`**, estrai tutto il contenuto e fai
doppio clic su `ERITA.cmd`. Non usare gli ZIP automatici **Source code** di
GitHub: non contengono né l'audio né le dipendenze complete.

### Cosa è cambiato

- un unico download e un unico punto di ingresso per l'utente;
- audio distribuito direttamente nella cartella `patch_data`;
- eliminato lo ZIP grande che prima stava annidato dentro il download;
- nessun `.exe` proprio del progetto e nessun Mod Engine;
- interfaccia, rilevamento di Steam e installazione guidata invariati;
- inventario e SHA-256 canonico dell'intero albero audio controllati prima
  dell'installazione;
- 8.969 WEM e 272 alias BNK, 9.241 file autenticati in totale.

L'albero audio occupa 605.706.607 byte e ha SHA-256 canonico
`8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb`.

### Audio e modalità online

Il contenuto è lo stesso payload corretto e autenticato della 0.9.4. Preserva i
clic del menu, gli eventi e i media di Elden Ring 1.17.1 ed è stato convalidato
in una sessione reale avviata normalmente da Steam, con Easy Anti-Cheat e
connessione online attivi. La 0.9.5 cambia l'impacchettamento di questo
contenuto, non il metodo applicato al gioco.

Il patcher non disattiva né modifica l'EAC. Limite noto: il metodo modifica
dati nei BDT senza riscrivere o rifirmare gli indici BHD. Le 8.973 risorse
modificate divergono dagli hash salted originali; l'installer accetta solo le
divergenze esatte del piano e del payload autenticati. Il test eseguito non è
una garanzia di rischio zero contro cambiamenti futuri del gioco, dell'EAC o
delle regole del servizio.

### Per chi ha installato la 0.8.4, la 0.9.1 o la 0.9.2

Usa prima **Correggi audio (ripristina)**. Se non c'è un backup valido, esegui
la verifica di integrità tramite Steam. Conferma l'audio originale e solo dopo
installa la 0.9.5. Quelle versioni vecchie non sono un'alternativa sicura.
