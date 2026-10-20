# Nota di sessione — 20 ottobre 2026: i filmati Bink

> Appunto di lavoro per riprendere in un'altra sessione (di Claude o di una persona). Non è
> un documento di riferimento: la procedura stabile sta in
> `doppiaggio/docs/GUIDA_FILMATI_TECNICA.pdf`. Base di partenza: `main` a `d3d8bbc`.
> **Committato in locale, non pushato**: in ERITA `c19891c` (script in `tools/filmati/` e
> questa nota), nel repo `doppiaggio` `480a1bc` (guide, pacchetto filmato, documenti).

## In breve

Si è partiti da un report diagnostico del patcher portoghese e si è arrivati alla procedura
completa per doppiare il **filmato iniziale** (`movie/10010010.bk2`), la cui voce sta dentro il
video e non nei file audio che il patcher sostituisce. La struttura del file è stata
verificata e confrontata con la versione doppiata portoghese. Per ricostruire l'audio servono
due script nuovi e RAD Video Tools. Le guide per chi coordina e per i doppiatori sono pronte,
e anche il pacchetto audio da mandare ai doppiatori. **Manca la voce italiana.**

---

## 1. Il report diagnostico (ERPT-PAYLOAD-001)

Report del patcher **upstream ERPT-BR 0.9.7**, non di ERITA: i messaggi sono in portoghese,
mentre in ERITA la stessa stringa è tradotta (`patcher/patch_data.py`, "Estensione inattesa
nel payload").

- Steam indicava il BuildID `25827938`, mentre quello atteso è `25080141`. Con il manifesto
  facoltativo (0.9.6+) l'installazione non si ferma per questo: la pre-verifica annota solo
  "Steam/online non confermati".
- La convalida del payload ha trovato `enus/wem/91/91235880.wav` dentro `patch_data`: sono
  ammessi solo `.wem` e `.bnk`. L'installazione si è fermata in sicurezza, con stato
  `patch_not_started`: nessun file del gioco è stato toccato.
- `91235880` è la narrazione di un finale (TalkMsg 20481000): qualcuno ci aveva messo un
  `.wav` al posto del `.wem`. Chi l'abbia messo non si sa.
- **Su questa postazione** il BuildID è `25827938`, ma gli SHA-256 di `sd.bhd` e
  `sd_dlc02.bhd` coincidono con il profilo 1.17.1 pinnato. Il patcher quindi accetta il gioco.

Prova successiva dell'utente con il payload PT-BR 0.9.7 installato: **le voci in gioco sono in
portoghese, l'intro resta in inglese**. È il comportamento atteso, perché la 0.9.x non scrive
mai in `movie/`.

## 2. Dove sta l'audio dei filmati

| filmato | voce | stato |
|---|---|---|
| intro `movie/10010010.bk2` | dentro il Bink, 5 tracce audio | da fare: argomento di questa sessione |
| finali `19000010/60/70/80.bk2` | il video non ha audio; la narrazione è Wwise nei banchi `s19_00_00xx` | già coperti dal payload audio |
| `13000050`, `19000030`, `60510000`, `movie_dlc/20010020` | dentro il Bink (sono nel pacchetto filmati portoghese 0.8.x) | da analizzare allo stesso modo |

## 3. Com'è fatta l'intro

`KB2n` (Bink 2), 3840×2160, 30 fps, 5550 fotogrammi, 184,982 s, 1.016.283.424 byte. Le tracce
audio sono tutte a 48 kHz, codifica Bink Audio DCT:

| ID | canali | kbit/s | ruolo (verificato) |
|---|---|--:|---|
| 0 | stereo | 104 | 5.1, anteriori |
| **1** | mono | 39 | **5.1, centrale: solo voce** (silenzio digitale nelle pause) |
| 2 | mono | 9 | 5.1, subwoofer |
| 3 | stereo | 88 | 5.1, surround |
| **4** | stereo | 138 | **mix stereo completo**, musica più voce |

- **Come lo sappiamo.** Un fit ai minimi quadrati dà
  ID4 ≈ 1,65·anteriori + 0,83·centrale + 0,33–0,42·surround − 1,4·LFE, con scarto −20 dB. Il
  coefficiente negativo del subwoofer è un artefatto del fit.
- **La voce entra nello stereo con peso costante ≈ 0,83.** Sottraendo 0,83·ID1 dall'ID 4,
  l'inglese residuo scende a circa −25 dB. Un filtro FIR non fa meglio.
- **Confronto con l'intro doppiata portoghese** (pacchetto filmati 0.8.x, copia
  dell'utente in OneDrive, cartella `…\d52fe823-…\ABRA AQUI E SUBSTITUA AS PASTAS MOVIE E MOVIE_DLC\`):
  - il video è identico byte per byte, quindi non è stato ricodificato;
  - gli ID 0, 2 e 3 sono identici;
  - l'ID 1 è passato da mono a stereo a 140 kbit/s e compare in ultima posizione;
  - anche l'ID 4 è sostituito;
  - l'intestazione (frame max e dimensioni decodificate) è aggiornata in modo coerente;
  - il file è cresciuto di 1,8 MB.
- **Conclusione: si sostituiscono gli ID 1 e 4, e conta l'ID, non la posizione.** Se si cambia
  solo l'ID 1, chi gioca in stereo sente ancora l'inglese.

## 4. Strumenti

- **RAD Video Tools**: scaricato dal sito ufficiale in `C:\Users\leand\Downloads\RADTools\RADTools.7z`.
  SHA1 verificato: `DACE86BB00B755FEA8A0002538FAD79E3FAEBDD6`. L'archivio è cifrato, con
  password `RAD`; su questa postazione serve 7-Zip, che non è installato.
  - Dalla documentazione RAD: con **Convert a file** e il campo *Input from track* si estrae una
    traccia; con **Mix in sound** e *Mix into Bink track ID* si sostituisce una traccia
    esistente.
  - **Non ancora verificato:** che la versione gratuita scriva Bink 2 senza ricomprimere il
    video.
  - Lo sviluppatore portoghese conferma che si usa lo strumento "Bink it", sostituendo l'ID
    della traccia inglese.
- **Script in `tools/filmati/`**. Usano Python 3.12 e numpy, e si lanciano con `python -I`:
  - `bk2_tracks.py`: legge ID e formato delle tracce e confronta due `.bk2`;
  - `bk2_header_diff.py`: confronta le intestazioni;
  - `wav_info.py`: dà formato, picchi e livello dei WAV;
  - `voice_segments.py`: produce la tabella dei tempi della voce;
  - `downmix_fit.py`: fa il fit dell'ID 4 sugli ID 0–3;
  - `make_id4.py`: genera l'ID 4 nuovo, con metodo A (ricostruito) e B (sottratto), e l'ID 1
    definitivo.
- **Controllo di `make_id4.py`:** passandogli la voce inglese come "voce nuova", il metodo B
  restituisce l'ID 4 originale **identico campione per campione**. Il metodo A va abbassato di
  ~3 dB per non saturare. **Il metodo predefinito è B.**
- Altri script di analisi usati in sessione (`wav_corr.py`, `voice_removal.py`) sono rimasti
  nella scratchpad e non sono necessari.

## 5. Cosa è stato prodotto, e dove

| cosa | dove | in git? |
|---|---|---|
| WAV estratti dall'utente (ID 0–4) | `D:\SteamLibrary\steamapps\common\ELDEN RING\Game\movie\10010010_id*.wav` | no: **da spostare fuori dalla cartella del gioco** |
| basi senza voce A e B, da ascoltare | `C:\Users\leand\Downloads\bk2-audio\10010010_id4_senza_voce_{A_ricostruito,B_sottratto}.wav` | no |
| pacchetto per i doppiatori | `C:\Users\leand\Downloads\bk2-audio\per-doppiatori\` (`01_guida_voce_inglese`, `02_base_musica_senza_voce` = B, `03_mix_originale_inglese`) | no |
| guida tecnica | `doppiaggio/docs/GUIDA_FILMATI_TECNICA.{html,pdf}` | sì (`doppiaggio`, `480a1bc`) |
| guida per i doppiatori | `doppiaggio/docs/GUIDA_FILMATI_DOPPIATORI.{html,pdf}` | sì (`doppiaggio`, `480a1bc`) |
| pacchetto filmato | `doppiaggio/pacchetti/Filmato_iniziale/`; zip in `doppiaggio/distribuzione/Pacchetti/` | sì, tranne i tre wav e lo zip (si rigenerano) |
| script | `tools/filmati/` | sì (ERITA, `c19891c`) |

Le guide seguono lo stile di `GUIDA_PACCHETTI.html`: stesso CSS, PDF stampato con Edge
headless come fa `doppiaggio/tools/guida.py`. Non sono generate da `guida.py`: per modificarle
si edita l'HTML e si ristampa (`msedge --headless=new --no-pdf-header-footer --print-to-pdf=…`).

**Cosa deve consegnare il doppiatore:** un solo `intro_voce_IT.wav`, mono, 48.000 Hz, 16 bit,
esattamente 8.879.112 campioni (3:04.982), con solo la voce, allineata all'inglese.

## 6. Easy Anti-Cheat

**Non verificato.** Il test online documentato riguarda solo l'audio in `sd/`. I `.bk2` sono
file sciolti, senza indici hash, quindi è plausibile che non siano controllati, ma non è una
garanzia. Indicazione data: provare offline e rimettere l'originale prima di andare online.

## 7. Lavori aperti

1. Spostare i WAV `10010010_id*.wav` fuori da `ELDEN RING\Game\movie\`.
2. Ascoltare le basi A e B e confermare il metodo (predefinito: B).
3. Installare 7-Zip ed estrarre RAD Video Tools. Al primo uso verificare che scriva Bink 2
   copiando il video, cioè che `bk2_tracks.py` dia `video: identico`.
4. **Aggiornamento di fine sessione: il pacchetto è pronto.** È in
   `doppiaggio/pacchetti/Filmato_iniziale/` e lo zip in
   `distribuzione/Pacchetti/Filmato_iniziale.zip`, ~85 MB (§16 del piano).
   - È un **pacchetto a parte** che segue `GUIDA_FILMATI_DOPPIATORI.pdf`: tre WAV di
     riferimento, la guida e `copione.html` con le 17 battute dei sottotitoli del gioco
     (`TalkMsg` 14000000–14000900 e 15000000–15000700). Si consegna un solo
     `intro_voce_IT.wav` su Drive, in *Consegne → Filmato_iniziale*.
   - Lo genera `doppiaggio/tools/make_packet_filmato.py`. `impacchetta.py` riconosce i
     pacchetti filmato da `filmato.json`.
   - La guida ora dice da dove si scarica il pacchetto e dove si consegna.
   - I punti di inizio delle battute sono stimati in `doppiaggio/fonti/filmato_10010010.csv`
     (`verificato=no`) e vanno confermati all'ascolto.
   - `docs/GUIDA_FILMATI_DOPPIATORI.pdf` è aggiornato, identico a quello nel pacchetto.
5. Con la voce italiana: `make_id4.py`, poi due passaggi di Mix in sound (ID 1 e ID 4),
   poi la verifica con gli script e la prova offline. Se possibile provare sia in stereo sia
   in 5.1.
6. Ripetere l'analisi sugli altri 4 filmati con voce.
7. Per ERITA (da progettare): il video resta identico, quindi si potrebbero distribuire solo le
   tracce audio codificate (pochi MB) e far ricostruire il `.bk2` al patcher partendo
   dall'originale dell'utente, con hash prima e dopo, manifesto, backup e ripristino. Oggi il
   patcher rifiuta qualunque `.bk2` (`optional_movie_payload_present`, `legacy_movie_sidecars`).
8. Decidere se committare `tools/filmati/` in ERITA (oppure spostarlo in `doppiaggio/tools/`)
   e le guide nel repo `doppiaggio`.

## Per continuare

- Leggere `doppiaggio/docs/GUIDA_FILMATI_TECNICA.pdf`, che contiene tutta la procedura.
- `python -I tools/filmati/bk2_tracks.py "<…>\Game\movie\10010010.bk2"` riproduce l'analisi
  delle tracce in pochi secondi.
- Percorsi di questa postazione: il gioco è in `D:\SteamLibrary\steamapps\common\ELDEN RING\Game`
  (non su C:), e gli strumenti in `doppiaggio/tools/` che assumono `/mnt/c/...` (WSL) qui
  non funzionano senza adattare il percorso.
