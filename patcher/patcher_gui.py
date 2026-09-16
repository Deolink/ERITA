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
import time
import webbrowser
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tkinter import TclError, filedialog, messagebox
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
    from .diagnostics import build_diagnostic_report
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
    from diagnostics import build_diagnostic_report


PATCHER_VERSION = "0.9.3"
SUPPORTED_GAME_VERSION = "1.17.1"
SUPPORTED_STEAM_BUILD_IDS = frozenset({"25080141"})
STEAM_APP_ID = "1245620"
PROJECT_URL = "https://github.com/Deolink/ERITA"
INCIDENT_URL = f"{PROJECT_URL}/blob/main/docs/INCIDENTE-0.9.1.md"
INSTALLATION_SUSPENDED = True
COMPATIBILITY_ISSUE_URL = (
    f"{PROJECT_URL}/issues/new?template=compatibilidade.yml"
)
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


@dataclass(frozen=True)
class SteamBuildInfo:
    """Resultado passivo da leitura do appmanifest da biblioteca selecionada."""

    build_id: str | None
    status: str


class UnsupportedBuildError(CompatibilityError):
    """Versione rifiutata; conserva se il rilevamento ha preceduto ogni scrittura."""

    code = "ERITA-COMPAT-001"

    def __init__(
        self, build_info: SteamBuildInfo, *, before_game_writes: bool
    ) -> None:
        self.build_info = build_info
        self.before_game_writes = before_game_writes
        found = (
            f"Steam BuildID {build_info.build_id}"
            if build_info.build_id
            else {
                "manifest_missing": "manifesto Steam non trovato",
                "manifest_unreadable": "manifesto Steam senza accesso in lettura",
                "buildid_missing": "manifesto Steam senza BuildID",
                "layout_unknown": "cartella fuori dalla struttura attesa di Steam",
            }.get(build_info.status, "Steam BuildID non identificato")
        )
        safety_message = (
            "Il patcher si è fermato prima di caricare i file audio. Nessun "
            "file è stato modificato."
            if before_game_writes
            else "La modifica è stata rilevata durante la rivalidazione di sicurezza. "
            "L'installazione non è stata confermata; conserva i backup e verifica i "
            "file tramite Steam prima di aprire il gioco."
        )
        super().__init__(
            f"VERSIONE DEL GIOCO NON SUPPORTATA [{self.code}]\n\n"
            f"Rilevato: {found}.\n"
            f"Supportato da ERITA {PATCHER_VERSION}: Elden Ring "
            f"{SUPPORTED_GAME_VERSION}, Steam BuildID "
            f"{', '.join(sorted(SUPPORTED_STEAM_BUILD_IDS))}.\n\n"
            "Questa versione non ha ancora un profilo compatibile. "
            f"{safety_message} Usa 'Copia "
            "diagnostica' per inviarci i dati tecnici senza informazioni personali."
        )


class InstallationSuspendedError(CompatibilityError):
    """Blocca nuove scritture finché il payload del build viene ricostruito."""

    code = "ERITA-AUDIO-001"

    def __init__(self) -> None:
        super().__init__(
            f"INSTALLAZIONE TEMPORANEAMENTE SOSPESA [{self.code}]\n\n"
            "Il pacchetto usato dalle versioni 0.9.1 e 0.9.2 sostituisce banchi "
            "audio più vecchi di quelli di Elden Ring 1.17.1 e può rimuovere suoni "
            "dell'interfaccia e delle cutscene. Nessun nuovo file verrà modificato.\n\n"
            "Se il doppiaggio è già stato installato, usa ora 'Correggi audio "
            "(ripristina)'. Se non ci fosse un backup valido, usa Steam > "
            "Proprietà > File installati > Verifica integrità. Non entrare in "
            "modalità online prima di aver ripristinato."
        )


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


def steam_build_info(game_dir: Path) -> SteamBuildInfo:
    """Legge passivamente il BuildID e conserva il motivo quando non esiste."""

    try:
        steamapps = game_dir.parents[2]
    except IndexError:
        return SteamBuildInfo(None, "layout_unknown")
    manifest_path = steamapps / f"appmanifest_{STEAM_APP_ID}.acf"
    try:
        content = manifest_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return SteamBuildInfo(None, "manifest_missing")
    except OSError:
        return SteamBuildInfo(None, "manifest_unreadable")
    match = re.search(r'"buildid"\s+"(\d+)"', content, re.IGNORECASE)
    if not match:
        return SteamBuildInfo(None, "buildid_missing")
    return SteamBuildInfo(match.group(1), "identified")


def steam_build_id(game_dir: Path) -> str | None:
    """Compatibilita': restituisce solo il BuildID, quando identificato."""

    return steam_build_info(game_dir).build_id


def require_supported_build(
    game_dir: Path,
    build_info: SteamBuildInfo | None = None,
    *,
    before_game_writes: bool = True,
) -> str:
    info = build_info or steam_build_info(game_dir)
    if info.build_id not in SUPPORTED_STEAM_BUILD_IDS:
        raise UnsupportedBuildError(
            info, before_game_writes=before_game_writes
        )
    return info.build_id


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
        self._closing = False
        self._report_collecting = 0
        self._diagnostic_lock = threading.Lock()
        self._log_history: deque[str] = deque(maxlen=120)
        self._diagnostic_operation = "idle"
        self._diagnostic_stage = "ready"
        self._diagnostic_stage_started = time.monotonic()
        self._diagnostic_stage_elapsed: int | None = None
        self._diagnostic_write_state = "not_started"
        self._diagnostic_progress = (0, 0)
        self._diagnostic_status = "Instalacao suspensa; restaure o audio original."
        self._detected_build_id: str | None = None
        self._build_read_status = "not_checked"
        self._detected_build_path_key: str | None = None
        self._last_error_code: str | None = None
        self._last_error_kind: str | None = None
        self._last_error_message: str | None = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        icon = Path(__file__).with_name("patcher.ico")
        if icon.is_file():
            try:
                self.iconbitmap(str(icon))
            except Exception:
                pass

        self.path_var = ctk.StringVar(value="")
        self.status_var = ctk.StringVar(
            value="Installazione sospesa; ripristina l'audio originale."
        )
        self.build_var = ctk.StringVar(
            value=f"ERITA {PATCHER_VERSION} | target: Elden Ring {SUPPORTED_GAME_VERSION}"
        )
        self._build_interface()
        detected = find_elden_ring()
        if detected:
            self._begin_operation("startup_check")
            self.path_var.set(str(detected))
            build_info = steam_build_info(detected)
            self._record_build_info(build_info, detected)
            self.build_var.set(
                f"ERITA {PATCHER_VERSION} | target {SUPPORTED_GAME_VERSION} / "
                f"build {', '.join(sorted(SUPPORTED_STEAM_BUILD_IDS))} | rilevato: "
                f"{build_info.build_id or 'non identificato'}"
            )
            try:
                pending = self._pending_transactions(detected)
            except (PatcherError, OSError) as exc:
                self._set_stage(
                    "startup_backup_check",
                    "Impossibile ispezionare i backup in sicurezza.",
                )
                self._record_error(exc)
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
                recovery_message = (
                    "Installazione precedente interrotta: ripristina o reinstalla "
                    "prima di aprire il gioco."
                )
                self._set_stage(
                    "recovery_required",
                    recovery_message,
                    write_state="recovery_required",
                )
                self._record_error(BackupError(recovery_message))
                self.after(
                    250,
                    lambda: messagebox.showwarning(
                        "Recupero necessario",
                        "È stata trovata un'installazione interrotta per questa cartella. "
                        "Non aprire ora il gioco. Usa 'Correggi audio (ripristina)'; "
                        "verrà usato il backup verificato.",
                    ),
                )
            elif self._last_error_code is None:
                self._set_stage(
                    "installation_suspended",
                    "Installazione sospesa; usa Correggi audio (ripristina).",
                    finished=True,
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
            self, fg_color="#321719", border_color="#9f3c43", border_width=1
        )
        notice.pack(fill="x", padx=30, pady=(0, 12))
        ctk.CTkLabel(
            notice,
            text=(
                "⚠ INSTALLAZIONE SOSPESA SU ELDEN RING 1.17.1\n"
                "Le versioni 0.9.1/0.9.2 possono rimuovere i clic del menu e i suoni delle cutscene.\n"
                "Se hai già installato, non entrare online: usa Correggi audio (ripristina)."
            ),
            justify="left",
            anchor="w",
            font=ctk.CTkFont("Segoe UI", 12),
            text_color="#ffd7d9",
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
            text="Installazione sospesa",
            height=42,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            fg_color="#5a3033",
            hover_color="#754046",
            text_color="#f1d7d8",
            command=self._start_install,
        )
        self.install_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.restore_button = ctk.CTkButton(
            action_row,
            text="Correggi audio (ripristina)",
            height=42,
            width=220,
            fg_color=GOLD,
            hover_color=GOLD_HOVER,
            text_color="#111116",
            command=self._start_restore,
        )
        self.restore_button.pack(side="left", padx=(0, 8))
        self.project_button = ctk.CTkButton(
            action_row,
            text="Dettagli",
            height=42,
            width=90,
            fg_color="#343449",
            hover_color="#484860",
            command=lambda: webbrowser.open(INCIDENT_URL),
        )
        self.project_button.pack(side="left")
        self.report_button = ctk.CTkButton(
            action_row,
            text="Diagnóstico",
            height=42,
            width=120,
            fg_color="#343449",
            hover_color="#484860",
            command=self._start_diagnostic_report,
        )
        self.report_button.pack(side="left", padx=(8, 0))

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

    @staticmethod
    def _diagnostic_path_key(value: str | Path | None) -> str | None:
        if value is None:
            return None
        try:
            raw = os.fspath(value)
            if not raw:
                return None
            return os.path.normcase(os.path.abspath(raw))
        except (OSError, TypeError, ValueError):
            return None

    def _record_build_info(
        self,
        info: SteamBuildInfo,
        game_dir: str | Path | None = None,
    ) -> None:
        with self._diagnostic_lock:
            self._detected_build_id = info.build_id
            self._build_read_status = info.status
            if game_dir is not None:
                self._detected_build_path_key = self._diagnostic_path_key(
                    game_dir
                )

    def _begin_operation(self, operation: str) -> None:
        with self._diagnostic_lock:
            self._diagnostic_operation = operation
            self._diagnostic_stage = "starting"
            self._diagnostic_stage_started = time.monotonic()
            self._diagnostic_stage_elapsed = None
            self._diagnostic_write_state = "not_started"
            self._diagnostic_progress = (0, 0)
            self._detected_build_id = None
            self._build_read_status = "not_checked"
            self._detected_build_path_key = None
            self._last_error_code = None
            self._last_error_kind = None
            self._last_error_message = None

    def _set_stage(
        self,
        stage: str,
        message: str,
        *,
        write_state: str | None = None,
        finished: bool = False,
    ) -> None:
        with self._diagnostic_lock:
            self._diagnostic_stage = stage
            self._diagnostic_stage_started = time.monotonic()
            self._diagnostic_stage_elapsed = 0 if finished else None
            if write_state is not None:
                self._diagnostic_write_state = write_state
            self._diagnostic_progress = (0, 0)
        self._status(message)

    def _record_error(self, exc: BaseException) -> tuple[str, str, str]:
        if isinstance(exc, UnsupportedBuildError):
            code = exc.code
            self._record_build_info(exc.build_info)
        elif isinstance(exc, InstallationSuspendedError):
            code = exc.code
        elif isinstance(exc, PermissionError):
            code = "ERPT-FS-001"
        elif isinstance(exc, PatchDataError):
            code = "ERPT-PAYLOAD-001"
        elif isinstance(exc, LegacyBackupError):
            code = "ERPT-BACKUP-002"
        elif isinstance(exc, BackupError):
            code = "ERPT-BACKUP-001"
        elif isinstance(exc, CompatibilityError):
            code = "ERPT-COMPAT-002"
        elif isinstance(exc, PatcherError):
            code = "ERPT-INSTALL-001"
        elif isinstance(exc, OSError):
            code = "ERPT-IO-001"
        elif isinstance(exc, ValueError):
            code = "ERPT-DATA-001"
        else:
            code = "ERPT-INTERNAL-001"
        kind = type(exc).__name__
        message = str(exc) or "Falha sem mensagem adicional."
        with self._diagnostic_lock:
            if self._diagnostic_stage_elapsed is None:
                self._diagnostic_stage_elapsed = max(
                    0, int(time.monotonic() - self._diagnostic_stage_started)
                )
            self._last_error_code = code
            self._last_error_kind = kind
            self._last_error_message = message
        return code, kind, message

    def _diagnostic_snapshot(
        self,
        selected_path: str | None = None,
    ) -> dict[str, object]:
        selected = (
            selected_path if selected_path is not None else self.path_var.get()
        ).strip()
        game_dir = Path(selected) if selected else None
        selected_path_key = self._diagnostic_path_key(selected)
        with self._diagnostic_lock:
            detected_build_id = self._detected_build_id
            build_status = self._build_read_status
            detected_build_path_key = self._detected_build_path_key
            operation = self._diagnostic_operation
            stage = self._diagnostic_stage
            elapsed = self._diagnostic_stage_elapsed
            if elapsed is None:
                elapsed = max(
                    0, int(time.monotonic() - self._diagnostic_stage_started)
                )
            write_state = self._diagnostic_write_state
            progress_current, progress_total = self._diagnostic_progress
            error_code = self._last_error_code
            error_kind = self._last_error_kind
            error_message = self._last_error_message
            log_lines = tuple(self._log_history)
            status = getattr(self, "_diagnostic_status", "")
        if selected_path_key != detected_build_path_key:
            detected_build_id = None
            build_status = "not_checked"
        return {
            "patcher_version": PATCHER_VERSION,
            "operation": operation,
            "stage": stage,
            "status": status,
            "error_code": error_code,
            "error_kind": error_kind,
            "error_message": error_message,
            "supported_game_version": SUPPORTED_GAME_VERSION,
            "supported_build_ids": tuple(SUPPORTED_STEAM_BUILD_IDS),
            "detected_build_id": detected_build_id,
            "build_status": build_status,
            "stage_elapsed_seconds": elapsed,
            "progress_current": progress_current,
            "progress_total": progress_total,
            "game_write_state": write_state,
            "game_dir": game_dir,
            "log_lines": log_lines,
        }

    def _diagnostic_report(
        self,
        selected_path: str | None = None,
    ) -> str:
        snapshot = self._diagnostic_snapshot(selected_path)
        return build_diagnostic_report(**snapshot)

    def _start_diagnostic_report(self) -> None:
        if self._report_collecting:
            return
        selected_path = self.path_var.get()
        snapshot = self._diagnostic_snapshot(selected_path)
        update_dialog = self._show_diagnostic_dialog(
            "Diagnostica di ERITA",
            "Rivedi il report prima di pubblicarlo.",
            None,
        )
        self._launch_diagnostic_collection(
            snapshot=snapshot,
            update_dialog=update_dialog,
        )

    def _launch_diagnostic_collection(
        self,
        *,
        snapshot: dict[str, object],
        update_dialog: Callable[[str | None, str | None], None],
    ) -> None:
        self._report_collecting += 1
        self.report_button.configure(state="disabled", text="Preparazione...")

        def collect() -> None:
            try:
                report = build_diagnostic_report(**snapshot)
            except Exception as exc:
                error = (
                    "Non è stato possibile costruire il report locale. Nessun dato è "
                    f"stato inviato. Codice interno: {type(exc).__name__}."
                )
                self._ui(lambda error=error: update_dialog(None, error))
            else:
                self._ui(lambda report=report: update_dialog(report, None))
            finally:
                self._ui(self._finish_diagnostic_collection)

        threading.Thread(target=collect, daemon=True).start()

    def _finish_diagnostic_collection(self) -> None:
        self._report_collecting = max(0, self._report_collecting - 1)
        if not self._report_collecting:
            self.report_button.configure(state="normal", text="Diagnóstico")

    def _show_failure_dialog(
        self, title: str, summary: str, snapshot: dict[str, object]
    ) -> None:
        update_dialog = self._show_diagnostic_dialog(title, summary, None)
        self._launch_diagnostic_collection(
            snapshot=snapshot,
            update_dialog=update_dialog,
        )

    def _show_diagnostic_dialog(
        self, title: str, summary: str, report: str | None
    ) -> Callable[[str | None, str | None], None]:
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("760x610")
        dialog.minsize(680, 520)
        dialog.configure(fg_color=BG)
        dialog.transient(self)

        ctk.CTkLabel(
            dialog,
            text=summary,
            justify="left",
            anchor="w",
            wraplength=700,
            text_color=TEXT,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
        ).pack(fill="x", padx=22, pady=(20, 10))
        ctk.CTkLabel(
            dialog,
            text=(
                "Niente viene inviato automaticamente. La segnalazione su GitHub sarà "
                "pubblica; rivedi il testo e non allegare salvataggi né file del gioco."
            ),
            justify="left",
            anchor="w",
            wraplength=700,
            text_color="#b9eadb",
        ).pack(fill="x", padx=22, pady=(0, 10))

        report_box = ctk.CTkTextbox(
            dialog,
            fg_color="#0d0d14",
            text_color="#d6d0c3",
            font=ctk.CTkFont("Consolas", 11),
            wrap="none",
        )
        report_box.pack(fill="both", expand=True, padx=22, pady=(0, 14))
        report_box.insert(
            "1.0",
            report
            or "Preparazione della diagnostica locale e sanitizzata...\n"
            "Il messaggio di errore qui sopra può già essere usato per il supporto.",
        )
        report_box.configure(state="disabled")
        report_holder = {"text": report}

        feedback = ctk.StringVar(value="")
        ctk.CTkLabel(
            dialog,
            textvariable=feedback,
            anchor="w",
            text_color=MUTED,
        ).pack(fill="x", padx=22, pady=(0, 5))

        def copy_report() -> bool:
            current_report = report_holder["text"]
            if current_report is None:
                feedback.set("Attendi che la diagnostica finisca.")
                return False
            self.clipboard_clear()
            self.clipboard_append(current_report)
            self.update_idletasks()
            feedback.set("Diagnostica copiata. Rivedila e incollala nel campo della issue.")
            return True

        def save_report() -> None:
            current_report = report_holder["text"]
            if current_report is None:
                feedback.set("Attendi che la diagnostica finisca.")
                return
            destination = filedialog.asksaveasfilename(
                parent=dialog,
                title="Salva diagnostica sanitizzata",
                defaultextension=".json",
                initialfile="ERITA-diagnostica.json",
                filetypes=(("Report JSON", "*.json"), ("Tutti i file", "*.*")),
            )
            if not destination:
                return
            try:
                Path(destination).write_text(
                    current_report, encoding="utf-8", newline="\n"
                )
            except OSError as exc:
                messagebox.showerror(
                    "Impossibile salvare",
                    f"Scegli un'altra posizione.\n\nDettaglio: {exc}",
                    parent=dialog,
                )
                return
            feedback.set("Diagnostica salvata nella posizione scelta.")

        def open_issue() -> None:
            if not copy_report():
                return
            opened = webbrowser.open(COMPATIBILITY_ISSUE_URL)
            feedback.set(
                "Modulo aperto; incolla la diagnostica e invia solo dopo averla rivista."
                if opened
                else "Copiata. Apri la pagina Issues del progetto per incollare la diagnostica."
            )

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=(0, 20))
        copy_button = ctk.CTkButton(
            buttons,
            text="Copia diagnostica",
            command=copy_report,
            fg_color=GOLD,
            hover_color=GOLD_HOVER,
            text_color="#111116",
        )
        copy_button.pack(side="left", padx=(0, 8))
        save_button = ctk.CTkButton(
            buttons,
            text="Salva report",
            command=save_report,
            fg_color="#343449",
            hover_color="#484860",
        )
        save_button.pack(side="left", padx=(0, 8))
        issue_button = ctk.CTkButton(
            buttons,
            text="Apri segnalazione",
            command=open_issue,
            fg_color="#245d4b",
            hover_color="#327760",
        )
        issue_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Chiudi",
            command=dialog.destroy,
            width=80,
            fg_color="#343449",
            hover_color="#484860",
        ).pack(side="right")
        action_buttons = (copy_button, save_button, issue_button)
        if report is None:
            for button in action_buttons:
                button.configure(state="disabled")

        def update_report(
            completed_report: str | None, error_message: str | None
        ) -> None:
            try:
                if not dialog.winfo_exists():
                    return
            except Exception:
                return
            report_box.configure(state="normal")
            report_box.delete("1.0", "end")
            if completed_report is not None:
                report_holder["text"] = completed_report
                report_box.insert("1.0", completed_report)
                feedback.set("Diagnostica pronta. Rivedila prima di condividerla.")
                for button in action_buttons:
                    button.configure(state="normal")
            else:
                report_box.insert(
                    "1.0",
                    error_message
                    or "Non è stato possibile preparare la diagnostica locale.",
                )
                feedback.set("Nulla è stato inviato.")
            report_box.configure(state="disabled")

        def focus_dialog() -> None:
            try:
                if dialog.winfo_exists():
                    dialog.focus_force()
            except TclError:
                return

        dialog.after(50, focus_dialog)
        return update_report

    def _on_close(self) -> None:
        if self._busy:
            messagebox.showwarning(
                "Operazione in corso",
                "Attendi il termine di copia, verifica e sostituzione dei file. Chiudere ora "
                "potrebbe interrompere la transazione.",
            )
            return
        self._closing = True
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
        if self._closing:
            return

        def guarded_callback() -> None:
            if not self._closing:
                callback()

        try:
            self.after(0, guarded_callback)
        except (RuntimeError, TclError):
            # La raccolta della diagnostica è daemon e può terminare dopo la finestra.
            return

    def _log(self, message: str) -> None:
        with self._diagnostic_lock:
            self._log_history.append(message.rstrip())

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
        with self._diagnostic_lock:
            self._diagnostic_status = message
        self._ui(lambda: self.status_var.set(message))

    def _progress(self, current: int, total: int) -> None:
        value = 0.0 if total <= 0 else max(0.0, min(1.0, current / total))
        with self._diagnostic_lock:
            self._diagnostic_progress = (current, total)
        self._ui(lambda: self.progress.set(value))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.install_button.configure(state=state)
        self.restore_button.configure(state=state)
        self.browse_button.configure(state=state)
        self.path_entry.configure(state=state)

    def _report_failure(
        self,
        *,
        title: str,
        exc: BaseException,
        selected_path: str,
        status_message: str,
        display_message: str | None = None,
    ) -> None:
        code, _kind, technical_message = self._record_error(exc)
        self._status(status_message)
        self._log(f"ERRORE [{code}]: {technical_message}")
        with self._diagnostic_lock:
            stage = self._diagnostic_stage
        summary = (
            f"{display_message or technical_message}\n\n"
            f"Codice per il supporto: {code}\n"
            f"Fase in cui si è fermato: {stage}\n\n"
            "Nessuna diagnostica è stata inviata automaticamente."
        )
        snapshot = self._diagnostic_snapshot(selected_path)
        self._ui(
            lambda: self._show_failure_dialog(title, summary, snapshot)
        )

    def _validated_context(self, selected_path: str) -> tuple[Path, str]:
        self._set_stage(
            "process_check",
            "Confirmando que Elden Ring e Easy Anti-Cheat estao fechados...",
        )
        blockers = running_blockers()
        if blockers:
            raise PatcherError(
                "Chiudi manualmente prima di continuare: " + ", ".join(blockers) + "."
            )
        self._set_stage("game_directory", "Validando a pasta do jogo...")
        game_dir = validate_game_directory(selected_path)
        self._set_stage("backup_check", "Verificando recuperacoes pendentes...")
        pending = self._pending_transactions(game_dir)
        if pending:
            self._log(
                "Rilevata una transazione interrotta. Verrà usato il backup verificato per "
                "completare questo recupero."
            )
        self._set_stage("steam_build", "Identificando a versao instalada pela Steam...")
        build_info = steam_build_info(game_dir)
        self._record_build_info(build_info, game_dir)
        return game_dir, require_supported_build(game_dir, build_info)

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
        require_supported_build(game_dir, before_game_writes=False)
        if optional_movie_payload_present(APP_ROOT):
            raise CompatibilityError(
                "Una cartella movie/movie_dlc è apparsa durante la preparazione. È "
                "stata rifiutata e nessun file del gioco è stato sostituito."
            )

    def _start_install(self) -> None:
        if self._busy:
            return
        selected_path = self.path_var.get().strip()
        self._begin_operation("install")
        self._set_busy(True)
        self.progress.set(0)
        threading.Thread(
            target=self._install_worker, args=(selected_path,), daemon=False
        ).start()

    def _install_worker(self, selected_path: str) -> None:
        try:
            game_dir, build_id = self._validated_context(selected_path)
            self._log(
                f"Steam build target riconosciuto: {build_id} (gioco {SUPPORTED_GAME_VERSION})"
            )

            if INSTALLATION_SUSPENDED:
                self._set_stage(
                    "installation_suspended",
                    "Installazione sospesa; nessun file verrà modificato.",
                    write_state="patch_not_started",
                )
                raise InstallationSuspendedError()

            self._set_stage(
                "optional_movies",
                "Verifica che il pacchetto contenga solo audio autenticato...",
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
            self._set_stage(
                "archive_validation",
                "Convalida dei file audio del gioco in corso...",
                write_state="recovery_may_run",
            )
            entry_count = engine.load_archives()
            with self._diagnostic_lock:
                self._diagnostic_write_state = "patch_not_started"
            self._log(f"Totale voci BHD convalidate: {entry_count}")
            self._set_stage(
                "legacy_backup_check",
                "Verifica di residui di installer precedenti...",
            )
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

            self._set_stage(
                "payload",
                "Convalida / recupero del pacchetto audio in corso...",
                write_state="patch_not_started",
            )
            payload_dir = ensure_patch_data(
                APP_ROOT,
                log=self._log,
                progress=self._progress,
            )
            self._log(f"Payload verificato: {payload_dir}")

            self._set_stage(
                "plan",
                "Costruzione e convalida del piano completo in corso...",
                write_state="patch_not_started",
            )
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

            self._set_stage(
                "precommit",
                "Riconvalida di gioco, EAC e Steam build prima della sostituzione...",
                write_state="patch_not_started",
            )
            self._precommit_guard(game_dir)

            self._set_stage(
                "apply",
                "Creazione del backup e preparazione dei file transazionali in corso...",
                write_state="transaction_active",
            )
            applied, unmatched = engine.apply_plan(plan, progress=self._progress)
            self._progress(1, 1)
            self._set_stage(
                "completed",
                "Doppiaggio installato in sicurezza.",
                write_state="committed",
                finished=True,
            )
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
            self._report_failure(
                title="ERITA - permesso negato",
                exc=exc,
                selected_path=selected_path,
                status_message="Permesso negato; nessun successo confermato.",
                display_message=message,
            )
        except (PatcherError, PatchDataError, OSError, ValueError) as exc:
            self._report_failure(
                title="ERITA - installazione interrotta",
                exc=exc,
                selected_path=selected_path,
                status_message="Installazione annullata in sicurezza.",
            )
        except Exception as exc:  # Errore inatteso: non annunciare mai un successo parziale.
            self._report_failure(
                title="ERITA - errore inatteso",
                exc=exc,
                selected_path=selected_path,
                status_message="Errore inatteso; nessun successo confermato.",
                display_message=(
                    "Errore inatteso. Non aprire il gioco finché non esegui di nuovo "
                    "l'installer o non verifichi i file tramite Steam."
                ),
            )
        finally:
            self._ui(lambda: self._set_busy(False))

    def _start_restore(self) -> None:
        if self._busy:
            return
        selected_path = self.path_var.get().strip()
        self._begin_operation("restore")
        self._set_busy(True)
        self.progress.set(0)
        threading.Thread(
            target=self._restore_worker, args=(selected_path,), daemon=False
        ).start()

    def _restore_worker(self, selected_path: str) -> None:
        try:
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
                self._set_stage(
                    "restore_validation",
                    "Convalida dei file e del backup del build attuale in corso...",
                    write_state="recovery_may_run",
                )
                engine.load_archives()
                self._set_stage(
                    "restore_apply",
                    "Ripristino e verifica dei file originali in corso...",
                    write_state="transaction_active",
                )
                engine.restore_current_backup()
                audio_restored = True
            except (PatcherError, OSError) as exc:
                failures.append(f"Audio: {exc}")

            self._progress(1, 1)
            if failures:
                details = "\n\n".join(failures)
                if audio_restored:
                    self._set_stage(
                        "restore_partial",
                        "Ripristino parziale; controlla i dettagli.",
                        write_state="partial_restore",
                    )
                    self._log(f"RIPRISTINO PARZIALE: {details}")
                    partial_error = BackupError(details)
                    self._report_failure(
                        title="ERITA - ripristino parziale",
                        exc=partial_error,
                        selected_path=selected_path,
                        status_message="Ripristino parziale; controlla i dettagli.",
                        display_message=(
                            "Parte dei file è stata ripristinata, ma l'operazione completa "
                            "non è stata confermata. Non aprire il gioco finché non riprovi "
                            "o non usi la verifica di Steam."
                        ),
                    )
                    return
                raise BackupError(details)

            self._set_stage(
                "restore_completed",
                "File originali ripristinati e verificati.",
                write_state="restored",
                finished=True,
            )
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
            self._report_failure(
                title="ERITA - ripristino interrotto",
                exc=exc,
                selected_path=selected_path,
                status_message="Ripristino non eseguito.",
            )
        except Exception as exc:
            self._report_failure(
                title="ERITA - errore inatteso nel ripristino",
                exc=exc,
                selected_path=selected_path,
                status_message=(
                    "Errore inatteso; il ripristino non è stato confermato."
                ),
                display_message=(
                    "Errore inatteso durante il ripristino. Non aprire il gioco finché "
                    "non esegui di nuovo il patcher o non verifichi i file tramite Steam."
                ),
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
