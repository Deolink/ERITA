#!/usr/bin/env python3
"""Interface do instalador em codigo-fonte do ERPT-BR."""

# O executavel legado baixa este arquivo de ``main`` e o executa com exec().
# Interrompa-o antes de importar qualquer modulo novo: o usuario deve migrar
# para o pacote source, que e auditavel e nao executa codigo remoto.
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
        "ERPT-BR - migracao necessaria",
        "Este executavel foi descontinuado por seguranca e nao aplicara o patch.\n\n"
        "Baixe o pacote 'source-win64.zip' na pagina Releases do projeto, "
        "extraia-o e execute ERPT-BR.cmd.\n\n"
        "Se uma versao antiga da dublagem ja foi instalada, primeiro use "
        "Steam > Elden Ring > Propriedades > Arquivos instalados > "
        "Verificar integridade dos arquivos.",
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

try:  # Suporta ``python -m patcher.patcher_gui`` e execucao direta do arquivo.
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
except ImportError:  # pragma: no cover - caminho usado pelo script interno
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
PROJECT_URL = "https://github.com/lorepamplona/ERPT-BR"
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
    "start_protected_game.exe": "Inicializador do Easy Anti-Cheat",
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
    """Le o BuildID do appmanifest pertencente a pasta Steam selecionada."""
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
        found = build_id or "nao identificado"
        raise CompatibilityError(
            "Build fora do alvo desta versao candidata. "
            f"Alvo esperado: {', '.join(sorted(SUPPORTED_STEAM_BUILD_IDS))} "
            f"(patch {SUPPORTED_GAME_VERSION}); encontrado: {found}. "
            "Atualize o jogo pela Steam ou aguarde uma versao nova do ERPT-BR. "
            "Nenhum arquivo foi alterado."
        )
    return build_id


def running_blockers() -> list[str]:
    """Detecta processos; nunca os encerra automaticamente."""
    if sys.platform != "win32":
        return []
    system_root = os.environ.get("SystemRoot")
    tasklist = Path(system_root, "System32", "tasklist.exe") if system_root else None
    if tasklist is None or not tasklist.is_file():
        raise PatcherError(
            "Nao foi possivel localizar o tasklist oficial do Windows. "
            "Nenhum arquivo sera alterado."
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
            "Nao foi possivel confirmar se Elden Ring/Easy Anti-Cheat estao "
            f"fechados. Nenhum arquivo sera alterado. Detalhe: {exc}"
        ) from exc
    if result.returncode != 0:
        raise PatcherError(
            "O Windows nao permitiu consultar os processos em execucao. "
            "Nenhum arquivo sera alterado; feche o jogo e tente novamente."
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
    """Detecta uma tentativa de pacote BK2 sem confiar que as pastas sao seguras."""

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
            # Arquivo no lugar da pasta, link quebrado ou acesso negado: deixe
            # o modulo seguro produzir um diagnostico, em vez de ignorar.
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
                f"O plano capturou duas identidades para o mesmo payload: {relative}."
            )
    if len(planned_hashes) != plan.payload_file_count:
        raise CompatibilityError(
            "O plano nao autenticou exatamente todos os arquivos de payload encontrados."
        )
    for write in plan.writes:
        relative = write.replacement.source_relative
        if planned_hashes.get(relative) != write.source_sha256:
            raise CompatibilityError(
                f"A gravacao planejada nao corresponde ao payload autenticado: {relative}."
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
        self.title("ERPT-BR - Dublagem PT-BR")
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
        self.status_var = ctk.StringVar(value="Pronto para verificar a instalacao.")
        self.build_var = ctk.StringVar(
            value=f"ERPT-BR {PATCHER_VERSION} | alvo: Elden Ring {SUPPORTED_GAME_VERSION}"
        )
        self._build_interface()
        detected = find_elden_ring()
        if detected:
            self.path_var.set(str(detected))
            build = steam_build_id(detected)
            self.build_var.set(
                f"ERPT-BR {PATCHER_VERSION} | jogo {SUPPORTED_GAME_VERSION} | "
                f"Steam build {build or 'nao identificado'}"
            )
            try:
                pending = self._pending_transactions(detected)
            except (PatcherError, OSError) as exc:
                self.status_var.set(
                    "Backups nao puderam ser inspecionados com seguranca."
                )
                self.after(
                    250,
                    lambda exc=exc: messagebox.showerror(
                        "ERPT-BR - backups inacessiveis",
                        "O patcher foi aberto, mas recusou a raiz de backups por "
                        "seguranca. Nenhum arquivo do jogo foi alterado.\n\n"
                        f"Detalhe: {exc}",
                    ),
                )
                pending = []
            if pending:
                self.status_var.set(
                    "Instalacao anterior interrompida: restaure ou reinstale antes de abrir o jogo."
                )
                self.after(
                    250,
                    lambda: messagebox.showwarning(
                        "Recuperacao necessaria",
                        "Foi encontrada uma instalacao interrompida para esta pasta. "
                        "Nao abra o jogo agora. Use 'Restaurar original' ou conclua "
                        "novamente a instalacao; o backup verificado sera usado.",
                    ),
                )

    def _build_interface(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(25, 12))
        ctk.CTkLabel(
            header,
            text="ELDEN RING  •  DUBLAGEM PT-BR",
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
                "✓ Patcher em código-fonte: sem EXE do mod, ME3 ou DLL injetada no jogo.\n"
                "O jogo continua sendo iniciado normalmente pela Steam/Easy Anti-Cheat.\n"
                "Alvo candidato 1.17.1: o smoke test online final ainda está pendente."
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
            text="Pasta do jogo (…/ELDEN RING/Game)",
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
            text="Selecionar",
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
            text="Instalar / atualizar dublagem",
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
            text="Restaurar original",
            height=42,
            width=170,
            fg_color="#343449",
            hover_color="#484860",
            command=self._start_restore,
        )
        self.restore_button.pack(side="left", padx=(0, 8))
        self.project_button = ctk.CTkButton(
            action_row,
            text="Projeto",
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
            "Modo seguro ativo. O programa nao baixa nem executa codigo remoto e nao encerra processos."
        )
        self._log(
            "Use sempre a mesma conta do Windows e restaure o audio antes de mover a biblioteca Steam."
        )

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta ELDEN RING/Game")
        if selected:
            self.path_var.set(selected)

    def _on_close(self) -> None:
        if self._busy:
            messagebox.showwarning(
                "Operacao em andamento",
                "Aguarde a copia, verificacao e troca dos arquivos terminar. Fechar agora "
                "pode interromper a transacao.",
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
                "Feche manualmente antes de continuar: " + ", ".join(blockers) + "."
            )
        game_dir = validate_game_directory(selected_path)
        pending = self._pending_transactions(game_dir)
        if pending:
            self._log(
                "Transacao interrompida detectada. O backup verificado sera usado para "
                "concluir esta recuperacao."
            )
        return game_dir, require_supported_build(game_dir)

    @staticmethod
    def _precommit_guard(game_dir: Path) -> None:
        blockers = running_blockers()
        if blockers:
            raise PatcherError(
                "O jogo ou o anti-cheat foi aberto durante a preparacao. Feche "
                "manualmente antes de tentar novamente: "
                + ", ".join(blockers)
                + ". Nenhum arquivo foi trocado."
            )
        require_supported_build(game_dir)
        if optional_movie_payload_present(APP_ROOT):
            raise CompatibilityError(
                "Uma pasta movie/movie_dlc apareceu durante a preparacao. Ela "
                "foi recusada e nenhum arquivo do jogo foi trocado."
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
            self._status("Validando o build do jogo...")
            game_dir, build_id = self._validated_context(selected_path)
            self._log(
                f"Steam build alvo reconhecido: {build_id} (jogo {SUPPORTED_GAME_VERSION})"
            )

            if optional_movie_payload_present(APP_ROOT):
                raise CompatibilityError(
                    "Esta versao candidata instala somente o audio. Foi encontrada "
                    "uma pasta movie/movie_dlc ao lado do instalador, mas o pacote "
                    "antigo de cutscenes nao possui manifesto criptografico publico. "
                    "Mova essas pastas para outro local e execute novamente. Nenhum "
                    "arquivo do jogo foi alterado."
                )

            engine = PatchEngine(
                game_dir,
                log=self._log,
                precommit_guard=lambda: self._precommit_guard(game_dir),
            )
            entry_count = engine.load_archives()
            self._log(f"Total de entradas BHD validadas: {entry_count}")
            legacy = sorted((game_dir / "sd").glob("sd*.bdt.original"))
            if legacy:
                names = ", ".join(path.name for path in legacy)
                raise LegacyBackupError(
                    f"Backup do instalador antigo encontrado ({names}). Antes de baixar "
                    "os dados, siga MIGRACAO.md: verifique a integridade pela Steam, "
                    "confirme o audio original e so entao remova o arquivo .original."
                )
            legacy_movies = legacy_movie_sidecars(game_dir)
            if legacy_movies:
                names = ", ".join(
                    str(path.relative_to(game_dir)) for path in legacy_movies
                )
                raise LegacyBackupError(
                    f"Backup antigo de cutscene encontrado ({names}). Antes de instalar, "
                    "siga MIGRACAO.md: verifique a integridade pela Steam, confirme os "
                    "arquivos originais e so entao remova os sidecars .bk2.original."
                )

            self._status("Validando / obtendo o pacote de audio...")
            payload_dir = ensure_patch_data(
                APP_ROOT,
                log=self._log,
                progress=self._progress,
            )
            self._log(f"Payload verificado: {payload_dir}")

            self._status("Montando e validando o plano completo...")
            plan = build_authenticated_plan(
                engine, payload_dir, progress=self._progress
            )
            self._log(
                f"Cobertura: {plan.matched_file_count}/{plan.payload_file_count} "
                f"({plan.match_ratio:.1%}); {len(plan.writes)} slots serao atualizados."
            )
            if plan.unmatched_files:
                preview = ", ".join(plan.unmatched_files[:5])
                suffix = "..." if len(plan.unmatched_files) > 5 else ""
                self._log(
                    f"Aviso: {len(plan.unmatched_files)} itens nao existem neste build: "
                    f"{preview}{suffix}"
                )

            self._status("Revalidando jogo, EAC e Steam build antes da troca...")
            self._precommit_guard(game_dir)

            self._status("Criando backup e preparando arquivos transacionais...")
            applied, unmatched = engine.apply_plan(plan, progress=self._progress)
            self._progress(1, 1)
            self._status("Dublagem instalada com seguranca.")
            self._log(
                f"Concluido: {applied} slots de audio verificados e aplicados; "
                f"{unmatched} sem alvo."
            )
            self._ui(
                lambda: messagebox.showinfo(
                    "Instalacao concluida",
                    "A dublagem de audio foi aplicada e verificada.\n\n"
                    "Abra o Elden Ring normalmente pela Steam; este instalador nao "
                    "substitui nem desativa o Easy Anti-Cheat.",
                )
            )
        except PermissionError as exc:
            message = (
                "O Windows negou acesso aos arquivos do jogo. Feche o jogo e o Easy "
                "Anti-Cheat. Configure uma biblioteca Steam gravavel pelo seu usuario "
                "ou ajuste somente a permissao da pasta do jogo; nao execute o patcher "
                f"como administrador.\n\nDetalhe: {exc}"
            )
            self._status("Sem permissao; nenhum sucesso foi confirmado.")
            self._log(f"ERRO: {message}")
            self._ui(lambda: messagebox.showerror("ERPT-BR", message))
        except (PatcherError, PatchDataError, OSError, ValueError) as exc:
            message = str(exc)
            self._status("Instalacao cancelada com seguranca.")
            self._log(f"ERRO: {message}")
            self._ui(lambda message=message: messagebox.showerror("ERPT-BR", message))
        except Exception as exc:  # Falha inesperada: nunca anunciar sucesso parcial.
            self._status("Falha inesperada; nenhum sucesso foi confirmado.")
            self._log(f"ERRO INESPERADO: {type(exc).__name__}: {exc}")
            self._ui(
                lambda exc=exc: messagebox.showerror(
                    "ERPT-BR",
                    "Falha inesperada. Nao abra o jogo ate executar novamente o instalador "
                    "ou verificar os arquivos pela Steam.\n\n"
                    f"Detalhe: {type(exc).__name__}: {exc}",
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
            self._status("Validando backup do build atual...")
            game_dir, build_id = self._validated_context(selected_path)
            self._log(f"Restauracao solicitada para o Steam build {build_id}.")
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
                    self._status("Restauracao parcial; confira os detalhes.")
                    self._log(f"RESTAURACAO PARCIAL: {details}")
                    self._ui(
                        lambda details=details: messagebox.showerror(
                            "Restauracao parcial",
                            "Parte dos arquivos foi restaurada, mas a operacao inteira "
                            "nao foi confirmada. Nao abra o jogo ate tentar novamente ou "
                            f"usar a verificacao da Steam.\n\n{details}",
                        )
                    )
                    return
                raise BackupError(details)

            self._status("Arquivos originais restaurados e verificados.")
            self._ui(
                lambda: messagebox.showinfo(
                    "Restauracao concluida",
                    "Todos os arquivos BDT desse backup foram restaurados e verificados.",
                )
            )
        except (
            BackupError,
            LegacyBackupError,
            CompatibilityError,
            PatcherError,
            OSError,
        ) as exc:
            self._status("Restauracao nao realizada.")
            self._log(f"ERRO: {exc}")
            self._ui(lambda exc=exc: messagebox.showerror("ERPT-BR", str(exc)))
        except Exception as exc:
            self._status("Falha inesperada; a restauracao nao foi confirmada.")
            self._log(f"ERRO INESPERADO: {type(exc).__name__}: {exc}")
            self._ui(
                lambda exc=exc: messagebox.showerror(
                    "ERPT-BR",
                    "Falha inesperada durante a restauracao. Nao abra o jogo ate "
                    "executar novamente o patcher ou verificar os arquivos pela Steam.\n\n"
                    f"Detalhe: {type(exc).__name__}: {exc}",
                )
            )
        finally:
            self._ui(lambda: self._set_busy(False))


def main() -> int:
    if sys.version_info < (3, 11):
        root = ctk.CTk()
        root.withdraw()
        messagebox.showerror("ERPT-BR", "Python 3.11 ou mais recente e necessario.")
        root.destroy()
        return 2
    app = PatcherApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
