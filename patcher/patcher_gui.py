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
        "Baixe o pacote ERPT-BR mais recente para o seu sistema na pagina Releases, "
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
import time
import webbrowser
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from tkinter import TclError, filedialog, messagebox
from typing import Callable
import customtkinter as ctk

try:  # Suporta ``python -m patcher.patcher_gui`` e execucao direta do arquivo.
    from .engine import (
        BHD_INTEGRITY_SCOPED_MOD,
        ArchiveFingerprint,
        ArchiveProfileError,
        BackupError,
        CompatibilityError,
        GameArchiveProfile,
        LegacyBackupError,
        PatchEngine,
        PatcherError,
        find_incomplete_backups,
        validate_game_archive_profile,
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
except ImportError:  # pragma: no cover - caminho usado pelo script interno
    from engine import (
        BHD_INTEGRITY_SCOPED_MOD,
        ArchiveFingerprint,
        ArchiveProfileError,
        BackupError,
        CompatibilityError,
        GameArchiveProfile,
        LegacyBackupError,
        PatchEngine,
        PatcherError,
        find_incomplete_backups,
        validate_game_archive_profile,
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


PATCHER_VERSION = "0.9.7"
SUPPORTED_GAME_VERSION = "1.17.1"
SUPPORTED_STEAM_BUILD_IDS = frozenset({"25080141"})
SUPPORTED_AUDIO_PROFILE = GameArchiveProfile(
    profile_id="elden-ring-1.17.1-audio",
    archives=(
        ArchiveFingerprint(
            stem="sd",
            bhd_sha256=(
                "c62ef231ebdcd91b09349496c6f1ff6f5bc32959cc59bbd0474f90d36b3eb5ec"
            ),
            bdt_size=2_308_921_312,
            original_bdt_sha256=(
                "2cfc747f4bafef625210a9f0abbdd47f2e076f2576757f31c3b4aeb2e063742d"
            ),
        ),
        ArchiveFingerprint(
            stem="sd_dlc02",
            bhd_sha256=(
                "f8e4be20c1fd1c04b7d287de95d455fe9dceb73d13aaab44450fc03a225dde7e"
            ),
            bdt_size=371_868_704,
            original_bdt_sha256=(
                "b7f590ea9c8dd9c4fedfb76204516e0c037321170c5c83302b777e58d96cb97c"
            ),
        ),
    ),
)
STEAM_APP_ID = "1245620"
PROJECT_URL = "https://github.com/lorepamplona/ERPT-BR"
DETAILS_URL = f"{PROJECT_URL}/releases/tag/v0.9.7"
# Chave de emergência: pode ser reativada sem remover o fluxo de restauração.
INSTALLATION_SUSPENDED = False
COMPATIBILITY_ISSUE_URL = (
    f"{PROJECT_URL}/issues/new?template=compatibilidade.yml"
)
INSTALLATION_SUCCESS_MESSAGE = (
    "A dublagem de audio foi aplicada e verificada.\n\n"
    "Abra o Elden Ring normalmente pela Steam; este instalador nao substitui "
    "nem desativa o Easy Anti-Cheat. O appmanifest e apenas informativo: "
    "confirme que a Steam reconhece e atualiza esta instalacao antes de jogar "
    "online."
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
UI_FONT = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
MONO_FONT = "Consolas" if sys.platform == "win32" else "DejaVu Sans Mono"

BLOCKING_EXECUTABLES = {
    "eldenring.exe": "Elden Ring",
    "start_protected_game.exe": "Inicializador do Easy Anti-Cheat",
    "easyanticheat.exe": "Easy Anti-Cheat",
    "easyanticheat_eos.exe": "Easy Anti-Cheat EOS",
    "easyanticheat_launcher.exe": "Easy Anti-Cheat Launcher",
    "easyanticheat_epic.exe": "Easy Anti-Cheat (Epic)",
}


@dataclass(frozen=True)
class SteamBuildInfo:
    """Resultado passivo da leitura do appmanifest da biblioteca selecionada."""

    build_id: str | None
    status: str


class GameFilesCompatibilityError(CompatibilityError):
    """Os arquivos reais nao correspondem ao perfil homologado do payload."""

    code = "ERPT-FILES-001"

    def __init__(self, detail: str, *, before_game_writes: bool) -> None:
        self.before_game_writes = before_game_writes
        safety_message = (
            "O patcher parou antes de carregar o payload. Nenhum arquivo foi alterado."
            if before_game_writes
            else "A mudanca foi detectada na revalidacao final. A troca dos arquivos "
            "nao foi autorizada."
        )
        super().__init__(
            f"ARQUIVOS DO JOGO NAO HOMOLOGADOS [{self.code}]\n\n"
            f"{detail}\n\n"
            "Copiar um appmanifest de outra versao nao atualiza o jogo e nao libera "
            "esta verificacao. Use a Steam para atualizar ou verificar a integridade "
            "dos arquivos. Uma versao antiga so pode ser suportada com perfil e "
            "payload proprios, reconstruidos e validados para os arquivos reais "
            "dela.\n\n"
            f"{safety_message}"
        )


class InstallationSuspendedError(CompatibilityError):
    """Bloqueia novas gravacoes quando a chave preventiva esta ativa."""

    code = "ERPT-AUDIO-001"

    def __init__(self) -> None:
        super().__init__(
            f"INSTALACAO TEMPORARIAMENTE SUSPENSA [{self.code}]\n\n"
            "A instalacao foi desativada preventivamente pelo projeto. Nenhum "
            "arquivo novo sera alterado.\n\n"
            "Use 'Corrigir audio (restaurar)' se precisar voltar aos arquivos "
            "originais. Se nao houver um backup valido, use Steam > Propriedades "
            "> Arquivos instalados > Verificar integridade."
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
                            for value_name in ("InstallPath", "SteamPath"):
                                try:
                                    value = winreg.QueryValueEx(key, value_name)[0]
                                except OSError:
                                    continue
                                if isinstance(value, str) and value.strip():
                                    roots.append(Path(value))
                    except OSError:
                        continue
        except ImportError:
            pass
        roots.extend(
            (Path(r"C:\Program Files (x86)\Steam"), Path(r"C:\Program Files\Steam"))
        )
    else:
        for variable in ("STEAM_COMPAT_CLIENT_INSTALL_PATH", "STEAM_HOME"):
            configured = os.environ.get(variable)
            if configured:
                configured_root = Path(configured).expanduser()
                if configured_root.is_absolute():
                    roots.append(configured_root)
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            xdg_root = Path(xdg_data).expanduser()
            if xdg_root.is_absolute():
                roots.append(xdg_root / "Steam")
        roots.extend(
            (
                Path.home() / ".steam" / "steam",
                Path.home() / ".steam" / "root",
                Path.home() / ".local" / "share" / "Steam",
                Path.home()
                / ".var"
                / "app"
                / "com.valvesoftware.Steam"
                / ".local"
                / "share"
                / "Steam",
                Path.home()
                / "snap"
                / "steam"
                / "common"
                / ".local"
                / "share"
                / "Steam",
            )
        )
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = _path_key(root)
        if key not in seen:
            unique.append(root)
            seen.add(key)
    return unique


def _path_key(path: str | Path) -> str:
    """Deduplica caminhos sem colapsar caixa em filesystems POSIX."""

    value = os.path.abspath(os.fspath(path))
    return value.casefold() if sys.platform == "win32" else value


def _steam_libraries(root: Path) -> list[Path]:
    libraries = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    try:
        content = vdf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return libraries
    for value in re.findall(r'"path"\s+"([^"]+)"', content):
        normalized = value.replace("\\\\", "\\") if sys.platform == "win32" else value
        candidate = Path(normalized).expanduser()
        if candidate.is_absolute():
            libraries.append(candidate)
    unique: list[Path] = []
    seen: set[str] = set()
    for library in libraries:
        key = _path_key(library)
        if key not in seen:
            unique.append(library)
            seen.add(key)
    return unique


def find_elden_ring() -> Path | None:
    for steam_root in _steam_roots():
        for library in _steam_libraries(steam_root):
            candidate = library / "steamapps" / "common" / "ELDEN RING" / "Game"
            if (candidate / "eldenring.exe").is_file() and (
                candidate / "sd" / "sd.bhd"
            ).is_file():
                # Preserve o caminho lexical da biblioteca. ``resolve()`` pode
                # atravessar uma junction e perder o ``steamapps`` que contem o
                # manifesto usado apenas para informar o BuildID auxiliar.
                return candidate.absolute()
    return None


def _manifest_build_info(manifest_path: Path) -> tuple[SteamBuildInfo, str | None]:
    """Le um appmanifest sem expor seu conteudo nem inferir compatibilidade."""

    try:
        content = manifest_path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return SteamBuildInfo(None, "manifest_missing"), None
    except OSError:
        return SteamBuildInfo(None, "manifest_unreadable"), None
    install_match = re.search(r'"installdir"\s+"([^"]+)"', content, re.IGNORECASE)
    install_dir = install_match.group(1) if install_match else None
    match = re.search(r'"buildid"\s+"(\d+)"', content, re.IGNORECASE)
    if not match:
        return SteamBuildInfo(None, "buildid_missing"), install_dir
    return SteamBuildInfo(match.group(1), "identified"), install_dir


def _same_directory_identity(left: Path, right: Path) -> bool:
    """Compara identidades reais e falha fechado se uma delas nao puder ser lida."""

    try:
        return left.samefile(right)
    except OSError:
        return False


def _direct_manifest_paths(
    game_dir: Path, game_path_hints: tuple[Path, ...]
) -> tuple[Path, ...]:
    paths: list[Path] = []
    seen: set[str] = set()
    for candidate in (game_dir, *game_path_hints):
        try:
            steamapps = candidate.parents[2]
        except IndexError:
            continue
        manifest = steamapps / f"appmanifest_{STEAM_APP_ID}.acf"
        key = _path_key(manifest)
        if key not in seen:
            paths.append(manifest)
            seen.add(key)
    return tuple(paths)


def steam_build_info(
    game_dir: Path, *, game_path_hints: tuple[Path, ...] = ()
) -> SteamBuildInfo:
    """Le o BuildID auxiliar apenas do manifesto ligado a esta pasta."""

    # Uma dica lexical serve apenas para reencontrar ``steamapps`` depois que
    # ``resolve()`` atravessa uma junction. Ela nao concede autoridade: precisa
    # continuar apontando para a mesma identidade fisica de ``game_dir`` em
    # todas as validacoes, inclusive no precommit.
    verified_hints = tuple(
        hint
        for hint in game_path_hints
        if _same_directory_identity(hint, game_dir)
    )
    direct_manifests = _direct_manifest_paths(game_dir, verified_hints)
    direct_missing = False
    direct_failures: list[str] = []
    saw_unlinked_manifest = False
    for manifest_path in direct_manifests:
        info, install_dir = _manifest_build_info(manifest_path)
        if info.status == "manifest_missing":
            direct_missing = True
            continue
        if info.status == "manifest_unreadable":
            direct_failures.append(info.status)
            continue
        if not install_dir:
            direct_failures.append("installdir_missing")
            continue
        registered_game = (
            manifest_path.parent / "common" / install_dir / "Game"
        )
        if _same_directory_identity(registered_game, game_dir):
            return info
        saw_unlinked_manifest = True

    # Se ``resolve()`` atravessou uma junction, recupere o manifesto pela lista
    # oficial de bibliotecas da Steam. So aceite quando a pasta registrada e a
    # pasta selecionada forem a mesma identidade no sistema de arquivos.
    seen_manifests = {
        _path_key(path) for path in direct_manifests
    }
    fallback_failures: list[str] = []
    for steam_root in _steam_roots():
        for library in _steam_libraries(steam_root):
            manifest_path = (
                library / "steamapps" / f"appmanifest_{STEAM_APP_ID}.acf"
            )
            key = _path_key(manifest_path)
            if key in seen_manifests:
                continue
            seen_manifests.add(key)
            info, install_dir = _manifest_build_info(manifest_path)
            if info.status == "manifest_missing":
                continue
            if info.status == "manifest_unreadable":
                fallback_failures.append(info.status)
                continue
            if not install_dir:
                fallback_failures.append("installdir_missing")
                continue
            registered_game = library / "steamapps" / "common" / install_dir / "Game"
            if _same_directory_identity(registered_game, game_dir):
                return info
            saw_unlinked_manifest = True

    if direct_failures:
        return SteamBuildInfo(None, direct_failures[0])
    if saw_unlinked_manifest:
        return SteamBuildInfo(None, "manifest_not_linked")
    if fallback_failures:
        return SteamBuildInfo(None, fallback_failures[0])
    if direct_missing or direct_manifests:
        return SteamBuildInfo(None, "manifest_missing")
    try:
        game_dir.parents[2]
    except IndexError:
        return SteamBuildInfo(None, "layout_unknown")
    return SteamBuildInfo(None, "manifest_missing")


def steam_build_id(game_dir: Path) -> str | None:
    """Compatibilidade: retorna somente o BuildID, quando identificado."""

    return steam_build_info(game_dir).build_id


def require_supported_build(
    game_dir: Path,
    build_info: SteamBuildInfo | None = None,
    *,
    before_game_writes: bool = True,
) -> str:
    info = build_info or steam_build_info(game_dir)
    try:
        profile_id = validate_game_archive_profile(
            game_dir,
            SUPPORTED_AUDIO_PROFILE,
        )
    except CompatibilityError as exc:
        raise GameFilesCompatibilityError(
            str(exc),
            before_game_writes=before_game_writes,
        ) from exc
    if info.build_id in SUPPORTED_STEAM_BUILD_IDS:
        return (
            f"pre-verificacao local {profile_id} (manifesto informa o BuildID esperado "
            f"{info.build_id}; Steam/online nao sao confirmados pelo manifesto)"
        )
    if info.build_id is not None:
        return (
            f"pre-verificacao local {profile_id} (manifesto informa BuildID "
            f"{info.build_id}; Steam/online nao confirmados)"
        )
    return f"pre-verificacao local {profile_id} (Steam/online nao confirmados)"


def running_blockers() -> list[str]:
    """Detecta processos; nunca os encerra automaticamente."""
    if sys.platform.startswith("linux"):
        return _linux_running_blockers()
    if sys.platform != "win32":
        raise PatcherError(
            f"O sistema {sys.platform!r} ainda nao possui verificacao segura de "
            "processos. Nenhum arquivo sera alterado."
        )
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


def _linux_process_name(value: bytes | str) -> str:
    if isinstance(value, bytes):
        value = os.fsdecode(value)
    value = value.strip().strip('"')
    if not value:
        return ""
    return re.split(r"[\\/]", value)[-1].casefold()


def _linux_running_blockers(proc_root: Path = Path("/proc")) -> list[str]:
    """Inspeciona processos do usuario no Linux/Proton e falha fechado."""

    try:
        current_uid = os.getuid()
        entries = list(proc_root.iterdir())
    except (AttributeError, OSError) as exc:
        raise PatcherError(
            "Nao foi possivel consultar /proc para confirmar que Elden Ring e "
            "Easy Anti-Cheat estao fechados. Nenhum arquivo sera alterado."
        ) from exc

    inspected = 0
    names: set[str] = set()
    for process_dir in entries:
        if not process_dir.name.isdecimal():
            continue
        try:
            if process_dir.stat().st_uid != current_uid:
                continue
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PatcherError(
                "Nao foi possivel confirmar a identidade de um processo em /proc. "
                "Nenhum arquivo sera alterado."
            ) from exc
        inspected += 1

        try:
            comm = (process_dir / "comm").read_bytes()[:4096]
            name = _linux_process_name(comm)
            if name:
                names.add(name)
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise PatcherError(
                "Nao foi possivel ler os processos do usuario em /proc. "
                "Nenhum arquivo sera alterado."
            ) from exc

        try:
            with (process_dir / "cmdline").open("rb") as stream:
                command_line = stream.read(64 * 1024 + 1)
            if len(command_line) > 64 * 1024:
                raise PatcherError(
                    "Uma linha de comando em /proc excedeu o limite seguro. "
                    "Nenhum arquivo sera alterado."
                )
            for argument in command_line.split(b"\0"):
                name = _linux_process_name(argument)
                if name:
                    names.add(name)
        except FileNotFoundError:
            continue
        except PermissionError as exc:
            raise PatcherError(
                "O Linux negou a leitura dos processos do usuario. Nenhum arquivo "
                "sera alterado."
            ) from exc
        except OSError as exc:
            raise PatcherError(
                "Falha ao consultar os processos do usuario no Linux. Nenhum "
                "arquivo sera alterado."
            ) from exc

    if inspected == 0:
        raise PatcherError(
            "Nenhum processo do usuario pode ser confirmado em /proc. Nenhum "
            "arquivo sera alterado."
        )

    blockers = [
        label
        for executable, label in BLOCKING_EXECUTABLES.items()
        if executable in names
    ]
    if any(
        name.startswith("easyanticheat") and name.endswith(".exe")
        for name in names
    ) and not any("Anti-Cheat" in label for label in blockers):
        blockers.append("Easy Anti-Cheat")
    return list(dict.fromkeys(blockers))


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
        self._diagnostic_status = (
            "Instalacao suspensa; restaure o audio original."
            if INSTALLATION_SUSPENDED
            else "Pronto para instalar a dublagem."
        )
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
            value=(
                "Instalacao suspensa; restaure o audio original."
                if INSTALLATION_SUSPENDED
                else "Pronto para instalar a dublagem."
            )
        )
        self.build_var = ctk.StringVar(
            value=f"ERPT-BR {PATCHER_VERSION} | alvo: Elden Ring {SUPPORTED_GAME_VERSION}"
        )
        self._build_interface()
        detected = find_elden_ring()
        if detected:
            self._begin_operation("startup_check")
            self.path_var.set(str(detected))
            build_info = steam_build_info(detected)
            self._record_build_info(build_info, detected)
            self.build_var.set(
                f"ERPT-BR {PATCHER_VERSION} | alvo {SUPPORTED_GAME_VERSION} / "
                "BuildID Steam auxiliar esperado "
                f"{', '.join(sorted(SUPPORTED_STEAM_BUILD_IDS))} | informado: "
                f"{build_info.build_id or 'nao identificado'}"
            )
            try:
                pending = self._pending_transactions(detected)
            except (PatcherError, OSError) as exc:
                self._set_stage(
                    "startup_backup_check",
                    "Backups nao puderam ser inspecionados com seguranca.",
                )
                self._record_error(exc)
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
                recovery_message = (
                    "Instalacao anterior interrompida: restaure ou reinstale antes "
                    "de abrir o jogo."
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
                        "Recuperacao necessaria",
                        "Foi encontrada uma instalacao interrompida para esta pasta. "
                        "Nao abra o jogo agora. Use 'Corrigir audio (restaurar)'; "
                        "o backup verificado sera usado.",
                    ),
                )
            elif self._last_error_code is None:
                self._finish_startup_status(detected, build_info)

    def _finish_startup_status(
        self,
        game_dir: Path,
        build_info: SteamBuildInfo,
    ) -> None:
        """Anuncia apenas a pre-verificacao; o engine autentica o BDT completo."""

        try:
            compatibility = require_supported_build(game_dir, build_info)
        except GameFilesCompatibilityError as error:
            self._set_stage(
                "game_files_unsupported",
                f"Arquivos do jogo nao homologados [{error.code}]; "
                "abra Diagnostico para copiar o relatorio.",
                finished=True,
            )
            self._record_error(error)
            return
        if INSTALLATION_SUSPENDED:
            self._set_stage(
                "installation_suspended",
                "Instalacao suspensa; use Corrigir audio (restaurar).",
                finished=True,
            )
            return
        ready_message = (
            "Pre-verificacao dos arquivos concluida; o manifesto informa o BuildID "
            "esperado, mas nao confirma Steam/online. Pronto para a validacao completa."
            if build_info.build_id in SUPPORTED_STEAM_BUILD_IDS
            else (
                "Pre-verificacao dos arquivos concluida; manifesto opcional e "
                "Steam/online nao confirmados. Pronto para a validacao completa."
            )
        )
        self._set_stage("ready", ready_message, finished=True)
        self._log(f"Pre-verificacao local concluida: {compatibility}.")

    def _build_interface(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=30, pady=(25, 12))
        ctk.CTkLabel(
            header,
            text="ELDEN RING  •  DUBLAGEM PT-BR",
            font=ctk.CTkFont(UI_FONT, 24, "bold"),
            text_color=GOLD,
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            textvariable=self.build_var,
            font=ctk.CTkFont(UI_FONT, 12),
            text_color=MUTED,
        ).pack(anchor="w", pady=(4, 0))

        notice = ctk.CTkFrame(
            self,
            fg_color="#321719" if INSTALLATION_SUSPENDED else "#172d24",
            border_color="#9f3c43" if INSTALLATION_SUSPENDED else "#39785b",
            border_width=1,
        )
        notice.pack(fill="x", padx=30, pady=(0, 12))
        ctk.CTkLabel(
            notice,
            text=(
                (
                    "⚠ INSTALAÇÃO TEMPORARIAMENTE SUSPENSA\n"
                    "Nenhum arquivo novo será alterado; a restauração continua disponível."
                )
                if INSTALLATION_SUSPENDED
                else (
                    "✓ ERPT-BR 0.9.7 PARA ELDEN RING 1.17.1\n"
                    "Pacote validado; os arquivos do jogo serão conferidos antes da instalação."
                )
            ),
            justify="left",
            anchor="w",
            font=ctk.CTkFont(UI_FONT, 12),
            text_color="#ffd7d9" if INSTALLATION_SUSPENDED else "#d8f4e4",
        ).pack(fill="x", padx=14, pady=10)

        path_card = ctk.CTkFrame(self, fg_color=CARD)
        path_card.pack(fill="x", padx=30, pady=(0, 12))
        ctk.CTkLabel(
            path_card,
            text="Pasta do jogo (…/ELDEN RING/Game)",
            text_color=TEXT,
            anchor="w",
            font=ctk.CTkFont(UI_FONT, 13, "bold"),
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
            text=(
                "Instalação suspensa"
                if INSTALLATION_SUSPENDED
                else "Instalar dublagem"
            ),
            height=42,
            font=ctk.CTkFont(UI_FONT, 13, "bold"),
            fg_color="#5a3033" if INSTALLATION_SUSPENDED else GOLD,
            hover_color="#754046" if INSTALLATION_SUSPENDED else GOLD_HOVER,
            text_color="#f1d7d8" if INSTALLATION_SUSPENDED else "#111116",
            command=self._start_install,
        )
        self.install_button.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.restore_button = ctk.CTkButton(
            action_row,
            text="Corrigir áudio (restaurar)",
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
            text="Detalhes",
            height=42,
            width=90,
            fg_color="#343449",
            hover_color="#484860",
            command=lambda: webbrowser.open(DETAILS_URL),
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
            font=ctk.CTkFont(UI_FONT, 12, "bold"),
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
            font=ctk.CTkFont(MONO_FONT, 11),
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        self.log_box.configure(state="disabled")
        self._log(
            "Modo seguro ativo. O programa nao baixa nem executa codigo remoto e nao encerra processos."
        )
        self._log(
            "Use sempre o mesmo usuario do sistema e restaure o audio antes de mover a biblioteca Steam."
        )

    def _browse(self) -> None:
        selected = filedialog.askdirectory(title="Selecione a pasta ELDEN RING/Game")
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
        if isinstance(exc, (GameFilesCompatibilityError, ArchiveProfileError)):
            code = exc.code
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
            "Diagnostico do ERPT-BR",
            "Revise o relatorio antes de publica-lo.",
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
        self.report_button.configure(state="disabled", text="Preparando...")

        def collect() -> None:
            try:
                report = build_diagnostic_report(**snapshot)
            except Exception as exc:
                error = (
                    "Nao foi possivel montar o relatorio local. Nenhum dado foi "
                    f"enviado. Codigo interno: {type(exc).__name__}."
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
            font=ctk.CTkFont(UI_FONT, 13, "bold"),
        ).pack(fill="x", padx=22, pady=(20, 10))
        ctk.CTkLabel(
            dialog,
            text=(
                "Nada e enviado automaticamente. O chamado no GitHub sera publico; "
                "revise o texto e nao anexe saves nem arquivos do jogo."
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
            font=ctk.CTkFont(MONO_FONT, 11),
            wrap="none",
        )
        report_box.pack(fill="both", expand=True, padx=22, pady=(0, 14))
        report_box.insert(
            "1.0",
            report
            or "Preparando o diagnostico local e sanitizado...\n"
            "A mensagem de erro acima ja pode ser usada para suporte.",
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
                feedback.set("Aguarde o diagnostico terminar.")
                return False
            self.clipboard_clear()
            self.clipboard_append(current_report)
            self.update_idletasks()
            feedback.set("Diagnostico copiado. Revise e cole no campo da issue.")
            return True

        def save_report() -> None:
            current_report = report_holder["text"]
            if current_report is None:
                feedback.set("Aguarde o diagnostico terminar.")
                return
            destination = filedialog.asksaveasfilename(
                parent=dialog,
                title="Salvar diagnostico sanitizado",
                defaultextension=".json",
                initialfile="ERPT-BR-diagnostico.json",
                filetypes=(("Relatorio JSON", "*.json"), ("Todos os arquivos", "*.*")),
            )
            if not destination:
                return
            try:
                Path(destination).write_text(
                    current_report, encoding="utf-8", newline="\n"
                )
            except OSError as exc:
                messagebox.showerror(
                    "Nao foi possivel salvar",
                    f"Escolha outro local.\n\nDetalhe: {exc}",
                    parent=dialog,
                )
                return
            feedback.set("Diagnostico salvo no local escolhido.")

        def open_issue() -> None:
            if not copy_report():
                return
            opened = webbrowser.open(COMPATIBILITY_ISSUE_URL)
            feedback.set(
                "Formulario aberto; cole o diagnostico e envie somente apos revisar."
                if opened
                else "Copiado. Abra a pagina Issues do projeto para colar o diagnostico."
            )

        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=22, pady=(0, 20))
        copy_button = ctk.CTkButton(
            buttons,
            text="Copiar diagnóstico",
            command=copy_report,
            fg_color=GOLD,
            hover_color=GOLD_HOVER,
            text_color="#111116",
        )
        copy_button.pack(side="left", padx=(0, 8))
        save_button = ctk.CTkButton(
            buttons,
            text="Salvar relatório",
            command=save_report,
            fg_color="#343449",
            hover_color="#484860",
        )
        save_button.pack(side="left", padx=(0, 8))
        issue_button = ctk.CTkButton(
            buttons,
            text="Abrir chamado",
            command=open_issue,
            fg_color="#245d4b",
            hover_color="#327760",
        )
        issue_button.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            buttons,
            text="Fechar",
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
                feedback.set("Diagnostico pronto. Revise antes de compartilhar.")
                for button in action_buttons:
                    button.configure(state="normal")
            else:
                report_box.insert(
                    "1.0",
                    error_message
                    or "O diagnostico local nao pôde ser preparado.",
                )
                feedback.set("Nada foi enviado.")
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
                "Operacao em andamento",
                "Aguarde a copia, verificacao e troca dos arquivos terminar. Fechar agora "
                "pode interromper a transacao.",
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
            # A coleta de diagnostico e daemon e pode terminar depois da janela.
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
        self._log(f"ERRO [{code}]: {technical_message}")
        with self._diagnostic_lock:
            stage = self._diagnostic_stage
        summary = (
            f"{display_message or technical_message}\n\n"
            f"Codigo para suporte: {code}\n"
            f"Etapa em que parou: {stage}\n\n"
            "Nenhum diagnostico foi enviado automaticamente."
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
                "Feche manualmente antes de continuar: " + ", ".join(blockers) + "."
            )
        self._set_stage("game_directory", "Validando a pasta do jogo...")
        lexical_game_dir = Path(selected_path).expanduser().absolute()
        game_dir = validate_game_directory(selected_path)
        self._set_stage("backup_check", "Verificando recuperacoes pendentes...")
        pending = self._pending_transactions(game_dir)
        if pending:
            self._log(
                "Transacao interrompida detectada. O backup verificado sera usado para "
                "concluir esta recuperacao."
            )
        self._set_stage(
            "steam_build",
            "Lendo o registro auxiliar da Steam e validando os arquivos do jogo...",
        )
        build_info = steam_build_info(
            game_dir,
            game_path_hints=(lexical_game_dir,),
        )
        self._record_build_info(build_info, game_dir)
        try:
            compatibility = require_supported_build(game_dir, build_info)
        except GameFilesCompatibilityError:
            if not pending:
                raise
            # O journal pode estar justamente no intervalo seguro em que o BDT
            # ativo foi renomeado para rollback. PatchEngine recupera e autentica
            # esse nome antes de repetir o perfil; nao use o manifesto como atalho.
            self._log(
                "O perfil local sera revalidado depois da recuperacao "
                "autenticada da transacao interrompida."
            )
            compatibility = "recuperacao transacional pendente"
        return game_dir, compatibility

    @staticmethod
    def _precommit_guard(
        game_dir: Path, selected_path: str | Path | None = None
    ) -> None:
        blockers = running_blockers()
        if blockers:
            raise PatcherError(
                "O jogo ou o anti-cheat foi aberto durante a preparacao. Feche "
                "manualmente antes de tentar novamente: "
                + ", ".join(blockers)
                + ". Nenhum arquivo foi trocado."
            )
        hints = (
            (Path(selected_path).expanduser().absolute(),)
            if selected_path is not None
            else ()
        )
        build_info = steam_build_info(game_dir, game_path_hints=hints)
        require_supported_build(
            game_dir,
            build_info,
            before_game_writes=False,
        )
        if optional_movie_payload_present(APP_ROOT):
            raise CompatibilityError(
                "Uma pasta movie/movie_dlc apareceu durante a preparacao. Ela "
                "foi recusada e nenhum arquivo do jogo foi trocado."
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
            game_dir, compatibility = self._validated_context(selected_path)
            self._log(
                f"Pre-verificacao local concluida: {compatibility} "
                f"(alvo {SUPPORTED_GAME_VERSION})"
            )

            if INSTALLATION_SUSPENDED:
                self._set_stage(
                    "installation_suspended",
                    "Instalacao suspensa; nenhum arquivo sera alterado.",
                    write_state="patch_not_started",
                )
                raise InstallationSuspendedError()

            self._set_stage(
                "optional_movies",
                "Verificando se o pacote contem somente audio autenticado...",
            )
            if optional_movie_payload_present(APP_ROOT):
                raise CompatibilityError(
                    "Esta versao instala somente o audio. Foi encontrada "
                    "uma pasta movie/movie_dlc ao lado do instalador, mas o pacote "
                    "antigo de cutscenes nao possui manifesto criptografico publico. "
                    "Mova essas pastas para outro local e execute novamente. Nenhum "
                    "arquivo do jogo foi alterado."
                )

            engine = PatchEngine(
                game_dir,
                log=self._log,
                precommit_guard=lambda: self._precommit_guard(
                    game_dir, selected_path
                ),
                archive_profile=SUPPORTED_AUDIO_PROFILE,
            )
            self._set_stage(
                "archive_validation",
                "Validando os arquivos de audio do jogo...",
                write_state="recovery_may_run",
            )
            entry_count = engine.load_archives()
            with self._diagnostic_lock:
                self._diagnostic_write_state = "patch_not_started"
            self._log(f"Total de entradas BHD validadas: {entry_count}")
            self._set_stage(
                "legacy_backup_check",
                "Verificando vestigios de instaladores anteriores...",
            )
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

            self._set_stage(
                "payload",
                "Validando / obtendo o pacote de audio...",
                write_state="patch_not_started",
            )
            payload_dir = ensure_patch_data(
                APP_ROOT,
                log=self._log,
                progress=self._progress,
            )
            self._log(f"Payload verificado: {payload_dir}")

            self._set_stage(
                "plan",
                "Montando e validando o plano completo...",
                write_state="patch_not_started",
            )
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

            self._set_stage(
                "precommit",
                "Revalidando arquivos do jogo, EAC e registro Steam antes da troca...",
                write_state="patch_not_started",
            )
            self._precommit_guard(game_dir, selected_path)

            self._set_stage(
                "apply",
                "Criando backup e preparando arquivos transacionais...",
                write_state="transaction_active",
            )
            applied, unmatched = engine.apply_plan(
                plan,
                progress=self._progress,
                bhd_integrity_mode=BHD_INTEGRITY_SCOPED_MOD,
            )
            self._progress(1, 1)
            self._set_stage(
                "completed",
                "Dublagem instalada com seguranca.",
                write_state="committed",
                finished=True,
            )
            self._log(
                f"Concluido: {applied} slots de audio verificados e aplicados; "
                f"{unmatched} sem alvo."
            )
            self._ui(
                lambda: messagebox.showinfo(
                    "Instalacao concluida",
                    INSTALLATION_SUCCESS_MESSAGE,
                )
            )
        except PermissionError as exc:
            platform_name = "Windows" if sys.platform == "win32" else "Linux"
            message = (
                f"O {platform_name} negou acesso aos arquivos do jogo. Feche o jogo e o Easy "
                "Anti-Cheat. Configure uma biblioteca Steam gravavel pelo seu usuario "
                "ou ajuste somente a permissao da pasta do jogo; nao execute o patcher "
                f"como administrador/root.\n\nDetalhe: {exc}"
            )
            self._report_failure(
                title="ERPT-BR - permissao negada",
                exc=exc,
                selected_path=selected_path,
                status_message="Sem permissao; nenhum sucesso foi confirmado.",
                display_message=message,
            )
        except (PatcherError, PatchDataError, OSError, ValueError) as exc:
            self._report_failure(
                title="ERPT-BR - instalacao interrompida",
                exc=exc,
                selected_path=selected_path,
                status_message="Instalacao cancelada com seguranca.",
            )
        except Exception as exc:  # Falha inesperada: nunca anunciar sucesso parcial.
            self._report_failure(
                title="ERPT-BR - falha inesperada",
                exc=exc,
                selected_path=selected_path,
                status_message="Falha inesperada; nenhum sucesso foi confirmado.",
                display_message=(
                    "Falha inesperada. Nao abra o jogo ate executar novamente o "
                    "instalador ou verificar os arquivos pela Steam."
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
            game_dir, compatibility = self._validated_context(selected_path)
            self._log(
                "Restauracao solicitada apos a pre-verificacao local: "
                f"{compatibility}."
            )
            failures: list[str] = []
            audio_restored = False

            engine = PatchEngine(
                game_dir,
                log=self._log,
                precommit_guard=lambda: self._precommit_guard(
                    game_dir, selected_path
                ),
                archive_profile=SUPPORTED_AUDIO_PROFILE,
            )
            try:
                self._set_stage(
                    "restore_validation",
                    "Validando os arquivos e o backup do perfil homologado...",
                    write_state="recovery_may_run",
                )
                engine.load_archives()
                self._set_stage(
                    "restore_apply",
                    "Restaurando e verificando os arquivos originais...",
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
                        "Restauracao parcial; confira os detalhes.",
                        write_state="partial_restore",
                    )
                    self._log(f"RESTAURACAO PARCIAL: {details}")
                    partial_error = BackupError(details)
                    self._report_failure(
                        title="ERPT-BR - restauracao parcial",
                        exc=partial_error,
                        selected_path=selected_path,
                        status_message="Restauracao parcial; confira os detalhes.",
                        display_message=(
                            "Parte dos arquivos foi restaurada, mas a operacao inteira "
                            "nao foi confirmada. Nao abra o jogo ate tentar novamente ou "
                            "usar a verificacao da Steam."
                        ),
                    )
                    return
                raise BackupError(details)

            self._set_stage(
                "restore_completed",
                "Arquivos originais restaurados e verificados.",
                write_state="restored",
                finished=True,
            )
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
            self._report_failure(
                title="ERPT-BR - restauracao interrompida",
                exc=exc,
                selected_path=selected_path,
                status_message="Restauracao nao realizada.",
            )
        except Exception as exc:
            self._report_failure(
                title="ERPT-BR - falha inesperada na restauracao",
                exc=exc,
                selected_path=selected_path,
                status_message=(
                    "Falha inesperada; a restauracao nao foi confirmada."
                ),
                display_message=(
                    "Falha inesperada durante a restauracao. Nao abra o jogo ate "
                    "executar novamente o patcher ou verificar os arquivos pela Steam."
                ),
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
    if os.environ.get("ERPTBR_GUI_SMOKE") == "1":
        app.update_idletasks()
        app.destroy()
        return 0
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
