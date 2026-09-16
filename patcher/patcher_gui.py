#!/usr/bin/env python3
"""Interfaccia dell'installatore in codice sorgente di ERITA."""

# L'eseguibile legacy scarica questo file da ``main`` e lo esegue con exec().
# Interrompilo prima di importare qualsiasi modulo nuovo: l'utente deve migrare
# al pacchetto source, che è verificabile e non esegue codice remoto.
import sys
from pathlib import Path as _EarlyPath

if (
    getattr(sys, "frozen", False)
    or "__compiled__" in globals()
    or _EarlyPath(sys.argv[0]).suffix.casefold() == ".exe"
):
    import tkinter as _legacy_tk
    from tkinter import messagebox as _legacy_messagebox

    _legacy_root = _legacy_tk.Tk()
    _legacy_root.withdraw()
    _legacy_messagebox.showwarning(
        "ERITA - migrazione necessaria",
        "Questo eseguibile è stato dismesso per sicurezza e non applicherà la patch.\n\n"
        "Scarica il pacchetto 'source-win64.zip' dalla pagina Releases del progetto, "
        "estrailo ed esegui ERITA.cmd.\n\n"
        "Se una vecchia versione del doppiaggio è già stata installata, usa prima "
        "Steam > Elden Ring > Proprietà > File installati > "
        "Verifica integrità dei file.",
    )
    _legacy_root.destroy()
    raise SystemExit(2)

import csv
import json
import os
import re
import subprocess
import threading
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Callable
import customtkinter as ctk

try:  # Supporta ``python -m patcher.patcher_gui`` e l'esecuzione diretta del file.
    from .engine import (
        BackupError,
        CompatibilityError,
        LegacyBackupError,
        PatchEngine,
        PatcherError,
        find_incomplete_backups,
        validate_game_directory,
    )
    from .patch_data import (
        PRODUCTION_PAYLOAD,
        PatchDataError,
        PayloadSpec,
        ensure_patch_data,
        validate_patch_directory,
    )
except ImportError:  # pragma: no cover - percorso usato dallo script interno
    from engine import (
        BackupError,
        CompatibilityError,
        LegacyBackupError,
        PatchEngine,
        PatcherError,
        find_incomplete_backups,
        validate_game_directory,
    )
    from patch_data import (
        PRODUCTION_PAYLOAD,
        PatchDataError,
        PayloadSpec,
        ensure_patch_data,
        validate_patch_directory,
    )


PATCHER_VERSION = "0.9.1"
SUPPORTED_GAME_VERSION = "1.17.1"
SUPPORTED_STEAM_BUILD_IDS = frozenset({"25080141"})
STEAM_APP_ID = "1245620"
PROJECT_URL = "https://github.com/Deolink/ERITA"
APP_ROOT = Path(__file__).resolve().parent.parent
MOVIE_FOLDERS = ("movie", "movie_dlc")

BG = "#0a0a0f"
CARD = "#141420"
CARD_LIGHT = "#1b1b2b"
GOLD = "#c8aa6e"
GOLD_HOVER = "#e0c478"
TEXT = "#f0e6d2"
MUTED = "#aaa394"

BLOCKING_EXECUTABLES = {
    "eldenring.exe": "Elden Ring",
    "start_protected_game.exe": "Avviatore dell'Easy Anti-Cheat",
    "easyanticheat.exe": "Easy Anti-Cheat",
    "easyanticheat_launcher.exe": "Easy Anti-Cheat Launcher",
    "easyanticheat_epic.exe": "Easy Anti-Cheat (Epic)",
}


def _steam_roots() -> list[Path]:
    roots: list[Path] = []
    if sys.platform == "win32":
        try:
            import winreg

            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (
                    r"SOFTWARE\Valve\Steam",
                    r"SOFTWARE\WOW6432Node\Valve\Steam",
                ):
                    try:
                        with winreg.OpenKey(hive, subkey) as key:
                            value = winreg.QueryValueEx(key, "InstallPath")[0]
                        roots.append(Path(value))
                    except OSError:
                        continue
        except ImportError:
            pass
        roots.extend(
            (Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam"))
        )
    else:
        roots.extend(
            (
                Path.home() / ".steam" / "steam",
                Path.home() / ".local" / "share" / "Steam",
            )
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root).casefold()
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def _steam_libraries(root: Path) -> list[Path]:
    libraries = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    try:
        content = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libraries
    for value in re.findall(r'"path"\s+"([^"]+)"', content):
        libraries.append(Path(value.replace("\\\\", "\\")))
    return libraries


def find_elden_ring() -> Path | None:
    for steam_root in _steam_roots():
        for library in _steam_libraries(steam_root):
            candidate = library / "steamapps" / "common" / "ELDEN RING" / "Game"
            if (candidate / "eldenring.exe").is_file() and (
                candidate / "sd" / "sd.bhd"
            ).is_file():
                return candidate.resolve()
    return None


def steam_build_id(game_dir: Path) -> str | None:
    """Legge il BuildID dall'appmanifest della cartella Steam selezionata."""
    try:
        steamapps = game_dir.parents[2]
    except IndexError:
        return None
    manifest_path = steamapps / f"appmanifest_{STEAM_APP_ID}.acf"
    try:
        content = manifest_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    match = re.search(r'"buildid"\s+"(\d+)"', content, re.IGNORECASE)
    return match.group(1) if match else None


def require_supported_build(game_dir: Path) -> str:
    build_id = steam_build_id(game_dir)
    if build_id not in SUPPORTED_STEAM_BUILD_IDS:
        found = build_id or "non identificato"
        raise CompatibilityError(
            "Build fuori dal target di questa versione candidata. "
            f"Target atteso: {', '.join(sorted(SUPPORTED_STEAM_BUILD_IDS))} "
            f"(patch {SUPPORTED_GAME_VERSION}); trovato: {found}. "
            "Aggiorna il gioco tramite Steam oppure attendi una nuova versione di ERITA. "
            "Nessun file è stato modificato."
        )
    return build_id


def running_blockers() -> list[str]:
    """Rileva i processi in esecuzione; non li termina mai automaticamente."""
    if sys.platform != "win32":
        return []
    system_root = os.environ.get("SystemRoot")
    tasklist = Path(system_root, "System32", "tasklist.exe") if system_root else None
    if tasklist is None or not tasklist.is_file():
        raise PatcherError(
            "Impossibile individuare il tasklist ufficiale di Windows. "
            "Nessun file sarà modificato."
        )
    try:
        result = subprocess.run(
            [str(tasklist), "/FO", "CSV", "/NH"],
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PatcherError(
            "Impossibile confermare che Elden Ring/Easy Anti-Cheat siano "
            f"chiusi. Nessun file sarà modificato. Dettaglio: {exc}"
        ) from exc
    if result.returncode != 0:
        raise PatcherError(
            "Windows non ha permesso di consultare i processi in esecuzione. "
            "Nessun file sarà modificato; chiudi il gioco e riprova."
        )
    names: set[str] = set()
    for row in csv.reader(result.stdout.splitlines()):
        if row:
            names.add(row[0].casefold())
    return [
        label
        for executable, label in BLOCKING_EXECUTABLES.items()
        if executable in names
    ]


def optional_movie_payload_present(root: Path) -> bool:
    """Rileva un tentativo di pacchetto BK2 senza dare per scontato che le cartelle siano sicure."""

    for folder_name in MOVIE_FOLDERS:
        directory = root / folder_name
        try:
            if any(
                entry.name.casefold().endswith(".bk2") for entry in directory.iterdir()
            ):
                return True
        except FileNotFoundError:
            continue
        except OSError:
            # File al posto della cartella, link rotto o accesso negato: lascia
            # che sia il modulo sicuro a produrre una diagnosi, invece di ignorare.
            if os.path.lexists(directory):
                return True
    return False


def legacy_movie_sidecars(game_dir: Path) -> list[Path]:
    result: list[Path] = []
    for folder_name in MOVIE_FOLDERS:
        directory = game_dir / folder_name
        try:
            result.extend(
                item
                for item in directory.iterdir()
                if item.name.casefold().endswith(".bk2.original")
            )
        except (FileNotFoundError, NotADirectoryError):
            continue
    return sorted(result, key=lambda item: str(item).casefold())


def build_authenticated_plan(
    patch_engine: PatchEngine,
    payload_dir: Path,
    *,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    progress: Callable[[int, int], None] | None = None,
):
    """Bind the plan's per-file hashes to the pinned canonical payload tree."""

    plan = patch_engine.build_plan(payload_dir, progress=progress)
    planned_hashes: dict[str, str] = {}
    for relative, digest in plan.payload_file_sha256:
        prior = planned_hashes.setdefault(relative, digest)
        if prior != digest:
            raise CompatibilityError(
                f"Il piano ha rilevato due identità per lo stesso payload: {relative}."
            )
    if len(planned_hashes) != plan.payload_file_count:
        raise CompatibilityError(
            "Il piano non ha autenticato esattamente tutti i file di payload trovati."
        )
    for write in plan.writes:
        relative = write.replacement.source_relative
        if planned_hashes.get(relative) != write.source_sha256:
            raise CompatibilityError(
                f"La scrittura pianificata non corrisponde al payload autenticato: {relative}."
            )
    # This validation intentionally happens after planning. If a file changed
    # before/during planning, the same hashing pass must satisfy both the pinned
    # tree and every per-file SHA captured above. Later changes are rejected by
    # apply_plan before their bytes are written.
    validate_patch_directory(
        payload_dir,
        spec=spec,
        progress=progress,
        expected_file_sha256=planned_hashes,
    )
    return plan


class PatcherApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("Elden Ring - Doppiaggio ITA")
        self.geometry("820x650")
        self.minsize(760, 600)
        self.configure(fg_color=BG)
        self._busy = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        icon = Path(__file__).with_name("patcher.ico")
        if icon.is_file():
            try:
                self.iconbitmap(str(icon))
            except Exception:
                pass

        self.path_var = ctk.StringVar(value="")
        self.status_var = ctk.StringVar(value="Pronto per verificare l'installazione.")
        self.build_var = ctk.StringVar(
            value=f"ERITA {PATCHER_VERSION} | target: Elden Ring {SUPPORTED_GAME_VERSION}"
        )
        self._build_interface()
        detected = find_elden_ring()
        if detected:
            self.path_var.set(str(detected))
            build = steam_build_id(detected)
            self.build_var.set(
                f"ERITA {PATCHER_VERSION} | gioco {SUPPORTED_GAME_VERSION} | "
                f"Steam build {build or 'non identificato'}"
            )
            try:
                pending = self._pending_transactions(detected)
            except (PatcherError, OSError) as exc:
                self.status_var.set(
                    "Impossibile ispezionare i backup in sicurezza."
                )
                self.after(
                    250,
                    lambda exc=exc: messagebox.showerror(
                        "Backup non accessibili",
                        "Il patcher è stato aperto, ma ha rifiutato la radice dei backup per "
                        "sicurezza. Nessun file del gioco è stato modificato.\n\n"
                        f"Dettaglio: {exc}",
                    ),
                )
                pending = []
            if pending:
                self.status_var.set(
                    "Installazione precedente interrotta: ripristina o reinstalla prima di aprire il gioco."
                )
                self.after(
                    250,
                    lambda: messagebox.showwarning(
                        "Recupero necessario",
                        "È stata trovata un'installazione interrotta per questa cartella. "
                        "Non aprire ora il gioco. Usa 'Ripristina originale' oppure completa "
                        "di nuovo l'installazione; verrà usato il backup verificato.",
                    ),
                )

    def _build_interface(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(25, 12))
        ctk.CTkLabel(
            header,
            text="ELDEN RING  •  DOPPIAGGIO ITA",
            font=ctk.CTkFont("Segoe UI", 24, "bold"),
            text_color=GOLD,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            textvariable=self.build_var,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=MUTED,
        ).pack(anchor="w", pady=(4, 0))

        notice = ctk.CTkFrame(
            self, fg_color="#12251f", border_color="#245d4b", border_width=1
        )
        notice.pack(fill="x", padx=30, pady=(0, 12))
        ctk.CTkLabel(
            notice,
            text=(
                "✓ Patcher in codice sorgente: nessun EXE del mod, ME3 o DLL iniettata nel gioco.\n"
                "Il gioco continua ad avviarsi normalmente tramite Steam/Easy Anti-Cheat.\n"
                "Target candidato 1.17.1: lo smoke test online finale è ancora in sospeso."
            ),
            justify="left",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color="#b9eadb",
        ).pack(fill="x", padx=14, pady=10)

        path_card = ctk.CTkFrame(self, fg_color=CARD)
        path_card.pack(fill="x", padx=30, pady=(0, 12))
        ctk.CTkLabel(
            path_card,
            text="Cartella del gioco (…/ELDEN RING/Game)",
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
        ).pack(fill="x", padx=16, pady=(13, 6))
        row = ctk.CTkFrame(path_card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 14))
        self.path_entry = ctk.CTkEntry(
            row,
            textvariable=self.path_var,
            height=36,
            fg_color=CARD_LIGHT,
            text_color=TEXT,
        )
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.browse_button = ctk.CTkButton(
            row,
            text="Seleziona",
            width=105,
            height=36,
            fg_color="#343449",
            hover_color="#484860",
            command=self._browse,
        )
        self.browse_button.pack(side="right")

        action_row = ctk.CTkFrame(self, fg_color="transparent")
        action_row.pack(fill="x", padx=30, pady=(0, 12))
        self.install_button = ctk.CTkButton(
            action_row,
            text="Installa / aggiorna doppiaggio",
            height=42,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color=GOLD,
            hover_color=GOLD_HOVER,
            text_color="#111116",
            command=self._start_install,
        )
        self.install_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.restore_button = ctk.CTkButton(
            action_row,
            text="Ripristina originale",
            height=42,
            width=170,
            fg_color="#343449",
            hover_color="#484860",
            command=self._start_restore,
        )
        self.restore_button.pack(side="left", padx=(0, 8))
        self.project_button = ctk.CTkButton(
            action_row,
            text="Progetto",
            height=42,
            width=90,
            fg_color="#343449",
            hover_color="#484860",
            command=lambda: webbrowser.open(PROJECT_URL),
        )
        self.project_button.pack(side="left")

        progress_card = ctk.CTkFrame(self, fg_color=CARD)
        progress_card.pack(fill="both", expand=True, padx=30, pady=(0, 25))
        self.status_label = ctk.CTkLabel(
            progress_card,
            textvariable=self.status_var,
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12, "bold"),
        )
        self.status_label.pack(fill="x", padx=16, pady=(14, 6))
        self.progress = ctk.CTkProgressBar(
            progress_card, height=10, fg_color="#27273a", progress_color=GOLD
        )
        self.progress.set(0)
        self.progress.pack(fill="x", padx=16, pady=(0, 10))
        self.log_box = ctk.CTkTextbox(
            progress_card,
            fg_color="#0d0d14",
            text_color="#d6d0c3",
            font=ctk.CTkFont("Consolas", 11),
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.log_box.configure(state="disabled")
        self._log(
            "Modalità sicura attiva. Il programma non scarica né esegue codice remoto e non termina processi."
        )
        self._log(
            "Usa sempre lo stesso account Windows e ripristina l'audio prima di spostare la libreria Steam."
        )

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Seleziona la cartella ELDEN RING/Game")
        if selected:
            self.path_var.set(selected)

    def _on_close(self) -> None:
        if self._busy:
            messagebox.showwarning(
                "Operazione in corso",
                "Attendi il termine di copia, verifica e sostituzione dei file. Chiudere ora "
                "potrebbe interrompere la transazione.",
            )
            return
        self.destroy()

    @staticmethod
    def _pending_transactions(game_dir: Path) -> list[Path]:
        expected = game_dir.resolve()
        result: list[Path] = []
        for manifest_path in find_incomplete_backups():
            try:
                value = json.loads(manifest_path.read_text(encoding="utf-8"))
                if not isinstance(value, dict) or not isinstance(
                    value.get("game_dir"), str
                ):
                    result.append(manifest_path)
                    continue
                recorded = Path(value["game_dir"]).resolve()
            except (OSError, json.JSONDecodeError, TypeError, AttributeError):
                result.append(manifest_path)
                continue
            if recorded == expected:
                result.append(manifest_path)
        return result

    def _ui(self, callback: Callable[[], None]) -> None:
        self.after(0, callback)

    def _log(self, message: str) -> None:
        def append() -> None:
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message.rstrip() + "\n")
            self.log_box.see("end")
            self.log_box.configure(state="disabled")

        if threading.current_thread() is threading.main_thread():
            append()
        else:
            self._ui(append)

    def _status(self, message: str) -> None:
        self._ui(lambda: self.status_var.set(message))

    def _progress(self, current: int, total: int) -> None:
        value = 0.0 if total <= 0 else max(0.0, min(1.0, current / total))
        self._ui(lambda: self.progress.set(value))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.install_button.configure(state=state)
        self.restore_button.configure(state=state)
        self.browse_button.configure(state=state)
        self.path_entry.configure(state=state)

    def _validated_context(self, selected_path: str) -> tuple[Path, str]:
        blockers = running_blockers()
        if blockers:
            raise PatcherError(
                "Chiudi manualmente prima di continuare: " + ", ".join(blockers) + "."
            )
        game_dir = validate_game_directory(selected_path)
        pending = self._pending_transactions(game_dir)
        if pending:
            self._log(
                "Rilevata una transazione interrotta. Verrà usato il backup verificato per "
                "completare questo recupero."
            )
        return game_dir, require_supported_build(game_dir)

    @staticmethod
    def _precommit_guard(game_dir: Path) -> None:
        blockers = running_blockers()
        if blockers:
            raise PatcherError(
                "Il gioco o l'anti-cheat è stato aperto durante la preparazione. Chiudilo "
                "manualmente prima di riprovare: "
                + ", ".join(blockers)
                + ". Nessun file è stato sostituito."
            )
        require_supported_build(game_dir)
        if optional_movie_payload_present(APP_ROOT):
            raise CompatibilityError(
                "Una cartella movie/movie_dlc è apparsa durante la preparazione. È "
                "stata rifiutata e nessun file del gioco è stato sostituito."
            )

    def _start_install(self) -> None:
        if self._busy:
            return
        selected_path = self.path_var.get().strip()
        self._set_busy(True)
        self.progress.set(0)
        threading.Thread(
            target=self._install_worker, args=(selected_path,), daemon=False
        ).start()

    def _install_worker(self, selected_path: str) -> None:
        try:
            self._status("Convalida del build del gioco in corso...")
            game_dir, build_id = self._validated_context(selected_path)
            self._log(
                f"Steam build target riconosciuto: {build_id} (gioco {SUPPORTED_GAME_VERSION})"
            )

            if optional_movie_payload_present(APP_ROOT):
                raise CompatibilityError(
                    "Questa versione candidata installa solo l'audio. È stata trovata "
                    "una cartella movie/movie_dlc accanto all'installer, ma il vecchio "
                    "pacchetto di cutscene non ha un manifesto crittografico pubblico. "
                    "Sposta quelle cartelle altrove ed esegui di nuovo. Nessun "
                    "file del gioco è stato modificato."
                )

            engine = PatchEngine(
                game_dir,
                log=self._log,
                precommit_guard=lambda: self._precommit_guard(game_dir),
            )
            entry_count = engine.load_archives()
            self._log(f"Totale voci BHD convalidate: {entry_count}")
            legacy = sorted((game_dir / "sd").glob("sd*.bdt.original"))
            if legacy:
                names = ", ".join(path.name for path in legacy)
                raise LegacyBackupError(
                    f"Trovato un backup del vecchio installer ({names}). Prima di scaricare "
                    "i dati, segui MIGRACAO.md: verifica l'integrità tramite Steam, "
                    "conferma l'audio originale e solo allora rimuovi il file .original."
                )
            legacy_movies = legacy_movie_sidecars(game_dir)
            if legacy_movies:
                names = ", ".join(
                    str(path.relative_to(game_dir)) for path in legacy_movies
                )
                raise LegacyBackupError(
                    f"Trovato un vecchio backup di cutscene ({names}). Prima di installare, "
                    "segui MIGRACAO.md: verifica l'integrità tramite Steam, conferma i "
                    "file originali e solo allora rimuovi i sidecar .bk2.original."
                )

            self._status("Convalida / recupero del pacchetto audio in corso...")
            payload_dir = ensure_patch_data(
                APP_ROOT,
                log=self._log,
                progress=self._progress,
            )
            self._log(f"Payload verificato: {payload_dir}")

            self._status("Costruzione e convalida del piano completo in corso...")
            plan = build_authenticated_plan(
                engine, payload_dir, progress=self._progress
            )
            self._log(
                f"Copertura: {plan.matched_file_count}/{plan.payload_file_count} "
                f"({plan.match_ratio:.1%}); {len(plan.writes)} slot verranno aggiornati."
            )
            if plan.unmatched_files:
                preview = ", ".join(plan.unmatched_files[:5])
                suffix = "..." if len(plan.unmatched_files) > 5 else ""
                self._log(
                    f"Avviso: {len(plan.unmatched_files)} elementi non esistono in questo build: "
                    f"{preview}{suffix}"
                )

            self._status("Riconvalida di gioco, EAC e Steam build prima della sostituzione...")
            self._precommit_guard(game_dir)

            self._status("Creazione del backup e preparazione dei file transazionali in corso...")
            applied, unmatched = engine.apply_plan(plan, progress=self._progress)
            self._progress(1, 1)
            self._status("Doppiaggio installato in sicurezza.")
            self._log(
                f"Completato: {applied} slot audio verificati e applicati; "
                f"{unmatched} senza destinazione."
            )
            self._ui(
                lambda: messagebox.showinfo(
                    "Installazione completata",
                    "Il doppiaggio audio è stato applicato e verificato.\n\n"
                    "Apri Elden Ring normalmente tramite Steam; questo installer non "
                    "sostituisce né disattiva l'Easy Anti-Cheat.",
                )
            )
        except PermissionError as exc:
            message = (
                "Windows ha negato l'accesso ai file del gioco. Chiudi il gioco e l'Easy "
                "Anti-Cheat. Configura una libreria Steam scrivibile dal tuo utente "
                "oppure modifica solo il permesso della cartella del gioco; non eseguire il patcher "
                f"come amministratore.\n\nDettaglio: {exc}"
            )
            self._status("Permesso negato; nessun successo confermato.")
            self._log(f"ERRORE: {message}")
            self._ui(lambda: messagebox.showerror("Errore", message))
        except (PatcherError, PatchDataError, OSError, ValueError) as exc:
            message = str(exc)
            self._status("Installazione annullata in sicurezza.")
            self._log(f"ERRORE: {message}")
            self._ui(lambda message=message: messagebox.showerror("Errore", message))
        except Exception as exc:  # Errore inatteso: non annunciare mai un successo parziale.
            self._status("Errore inatteso; nessun successo confermato.")
            self._log(f"ERRORE INATTESO: {type(exc).__name__}: {exc}")
            self._ui(
                lambda exc=exc: messagebox.showerror(
                    "Errore",
                    "Errore inatteso. Non aprire il gioco finché non esegui di nuovo l'installer "
                    "o non verifichi i file tramite Steam.\n\n"
                    f"Dettaglio: {type(exc).__name__}: {exc}",
                )
            )
        finally:
            self._ui(lambda: self._set_busy(False))

    def _start_restore(self) -> None:
        if self._busy:
            return
        selected_path = self.path_var.get().strip()
        self._set_busy(True)
        self.progress.set(0)
        threading.Thread(
            target=self._restore_worker, args=(selected_path,), daemon=False
        ).start()

    def _restore_worker(self, selected_path: str) -> None:
        try:
            self._status("Convalida del backup del build attuale in corso...")
            game_dir, build_id = self._validated_context(selected_path)
            self._log(f"Ripristino richiesto per lo Steam build {build_id}.")
            failures: list[str] = []
            audio_restored = False

            engine = PatchEngine(
                game_dir,
                log=self._log,
                precommit_guard=lambda: self._precommit_guard(game_dir),
            )
            try:
                engine.load_archives()
                engine.restore_current_backup()
                audio_restored = True
            except (PatcherError, OSError) as exc:
                failures.append(f"Audio: {exc}")

            self._progress(1, 1)
            if failures:
                details = "\n\n".join(failures)
                if audio_restored:
                    self._status("Ripristino parziale; controlla i dettagli.")
                    self._log(f"RIPRISTINO PARZIALE: {details}")
                    self._ui(
                        lambda details=details: messagebox.showerror(
                            "Ripristino parziale",
                            "Parte dei file è stata ripristinata, ma l'operazione completa "
                            "non è stata confermata. Non aprire il gioco finché non riprovi o "
                            f"non usi la verifica di Steam.\n\n{details}",
                        )
                    )
                    return
                raise BackupError(details)

            self._status("File originali ripristinati e verificati.")
            self._ui(
                lambda: messagebox.showinfo(
                    "Ripristino completato",
                    "Tutti i file BDT di questo backup sono stati ripristinati e verificati.",
                )
            )
        except (
            BackupError,
            LegacyBackupError,
            CompatibilityError,
            PatcherError,
            OSError,
        ) as exc:
            self._status("Ripristino non eseguito.")
            self._log(f"ERRORE: {exc}")
            self._ui(lambda exc=exc: messagebox.showerror("Errore", str(exc)))
        except Exception as exc:
            self._status("Errore inatteso; il ripristino non è stato confermato.")
            self._log(f"ERRORE INATTESO: {type(exc).__name__}: {exc}")
            self._ui(
                lambda exc=exc: messagebox.showerror(
                    "Errore",
                    "Errore inatteso durante il ripristino. Non aprire il gioco finché non "
                    "esegui di nuovo il patcher o non verifichi i file tramite Steam.\n\n"
                    f"Dettaglio: {type(exc).__name__}: {exc}",
                )
            )
        finally:
            self._ui(lambda: self._set_busy(False))


def main() -> int:
    if sys.version_info < (3, 11):
        root = ctk.CTk()
        root.withdraw()
        messagebox.showerror("Errore", "È necessario Python 3.11 o più recente.")
        root.destroy()
        return 2
    app = PatcherApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
