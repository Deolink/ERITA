## 🚨 Hotfix di recupero — installazione sospesa

Questa versione impedisce nuove installazioni del pacchetto incompatibile con
Elden Ring 1.17.1 e mantiene il ripristino in un clic per chi ha installato la
0.9.1/0.9.2.

- Blocca l'installazione prima di scaricare il payload o modificare i file del gioco.
- Mette in evidenza **Correggi audio (ripristina)** come azione principale.
- Mostra il codice esplicito `ERITA-AUDIO-001` nella diagnostica.
- Mantiene il backup transazionale e il ripristino byte per byte.
- Documenta l'incompatibilità trovata in `cs_main.bnk` e `cs_m41.bnk`.
- Aggiunge la verifica degli hash salted registrati negli indici BHD.

### Per chi ha già installato

1. Non entrare ancora in modalità online.
2. Apri `ERITA.cmd`.
3. Clicca su **Correggi audio (ripristina)**.
4. Se non ci fosse un backup valido, usa **Steam > Elden Ring > Proprietà >
   File installati > Verifica integrità**.

Non usare la versione 0.8.4 come alternativa: contiene lo stesso vecchio
pacchetto audio. L'installazione sarà riattivata solo dopo che i banchi
saranno stati ricostruiti sulla versione 1.17.1 e i test di menu, battute,
cutscene ed EAC saranno stati completati.
