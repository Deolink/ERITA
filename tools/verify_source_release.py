#!/usr/bin/env python3
"""Convalida in modo indipendente l'unico ZIP finale di ERITA."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import stat
import struct
import unicodedata
import zipfile
import zlib
from pathlib import Path, PurePosixPath


SOURCE_FILES = frozenset(
    {
        "ERITA.cmd",
        "interno/INSTALAR_AMBIENTE.cmd",
        "interno/ABRIR_INTERFACE.cmd",
        "README.md",
        "MIGRACAO.md",
        "docs/INCIDENTE-0.9.1.md",
        "SECURITY.md",
        "THIRD_PARTY_NOTICES.md",
        "LICENSE",
        "patcher/__init__.py",
        "patcher/bnk.py",
        "patcher/engine.py",
        "patcher/diagnostics.py",
        "patcher/patch_data.py",
        "patcher/patcher_gui.py",
        "patcher/patcher.ico",
        "patcher/requirements-win64.lock",
    }
)
WHEEL_SHA256 = {
    "wheelhouse/customtkinter-5.2.2-py3-none-any.whl": (
        "14ad3e7cd3cb3b9eb642b9d4e8711ae80d3f79fb82545ad11258eeffb2e6b37c"
    ),
    "wheelhouse/darkdetect-0.8.0-py3-none-any.whl": (
        "a7509ccf517eaad92b31c214f593dbcf138ea8a43b2935406bbd565e15527a85"
    ),
    "wheelhouse/packaging-26.3-py3-none-any.whl": (
        "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c"
    ),
    "wheelhouse/pycryptodome-3.23.0-cp37-abi3-win_amd64.whl": (
        "c75b52aacc6c0c260f204cbdd834f76edc9fb0d8e0da9fbf8352ef58202564e2"
    ),
}
FINAL_VERSION = "v0.9.7"
FINAL_ARCHIVE_NAME = "ERITA-v0.9.7-Windows.zip"
PAYLOAD_TREE_SHA256 = "e97467e8ebbd1da87be96a44e4a2ee5694cd41c0bf592159b0570258d0b8460e"
PAYLOAD_FILE_COUNT = 9_240
PAYLOAD_WEM_COUNT = 8_968
PAYLOAD_BNK_COUNT = 272
PAYLOAD_UNCOMPRESSED_SIZE = 605_607_009
PAYLOAD_MAX_FILE_SIZE = 74_956_066
SELLEN_VANILLA_WEM_ID = "553755359"
STREAM_CHUNK_SIZE = 1024 * 1024
ARCHIVE_TIMESTAMP = (2020, 1, 1, 0, 0, 0)

EXPECTED_FILES = SOURCE_FILES | frozenset(WHEEL_SHA256)
FORBIDDEN_SUFFIXES = {".exe", ".dll", ".bat", ".ps1", ".scr", ".com"}
FORBIDDEN_ARCHIVE_SUFFIXES = {
    ".7z",
    ".bz2",
    ".cab",
    ".gz",
    ".iso",
    ".jar",
    ".rar",
    ".tar",
    ".tbz",
    ".tbz2",
    ".tgz",
    ".txz",
    ".xz",
    ".zip",
}
# Ordinary source/wheel members have narrow limits. Payload members are
# individually bounded and their aggregate uncompressed tree is exact.
MAX_MEMBER_SIZE = 5 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 8 * 1024 * 1024
MAX_TOTAL_COMPRESSED = 8 * 1024 * 1024
MAX_ARCHIVE_SIZE = 8 * 1024 * 1024
MAX_PAYLOAD_COMPRESSED = PAYLOAD_UNCOMPRESSED_SIZE + 1024 * 1024
MAX_FINAL_ARCHIVE_SIZE = MAX_PAYLOAD_COMPRESSED + MAX_ARCHIVE_SIZE
FORBIDDEN_SOURCE_PATTERNS = {
    "exec(compile(": "esecuzione dinamica di codice",
    "taskkill": "terminazione forzata di processi",
    "shellexecutew": "auto-elevazione UAC",
    "pyinstaller": "impacchettatore eseguibile",
    "nuitka": "impacchettatore eseguibile",
    "invoke-expression": "esecuzione dinamica di PowerShell",
    "-encodedcommand": "comando PowerShell codificato",
    "-executionpolicy bypass": "aggiramento della policy di PowerShell",
    "--ignore-security-hash": "aggiramento dell'hash di sicurezza di WinGet",
    "installallusers=1": "installazione globale con elevazione",
    "-verb runas": "auto-elevazione UAC",
    "http://": "download senza HTTPS",
    "erita_dev_unsafe_skip_payload_pin": "bypass di sviluppo della convalida del payload",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _verify_gui_controls(gui_source: str) -> None:
    """Impedisce di promuovere una GUI tornata per errore alla modalità BHD rigorosa."""

    required = (
        f'PATCHER_VERSION = "{FINAL_VERSION.removeprefix("v")}"',
        "INSTALLATION_SUSPENDED = False",
        "BHD_INTEGRITY_SCOPED_MOD",
        "bhd_integrity_mode=BHD_INTEGRITY_SCOPED_MOD",
        '"easyanticheat_eos.exe": "Easy Anti-Cheat EOS"',
    )
    missing = [control for control in required if control not in gui_source]
    if missing:
        raise SystemExit(
            f"Controlli obbligatori assenti dall'interfaccia: {missing}"
        )


def _safe_payload_relative(name: str) -> str:
    prefix = "patch_data/"
    if not name.startswith(prefix):
        raise SystemExit(f"Layout inatteso nel payload: {name!r}")
    relative = name[len(prefix) :]
    if not relative or "\\" in relative or ":" in relative or "\x00" in relative:
        raise SystemExit(f"Percorso non sicuro nel payload: {name!r}")
    parts = relative.split("/")
    path = PurePosixPath(*parts)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or path.as_posix() != relative
        or unicodedata.normalize("NFC", relative) != relative
        or any(part.endswith((" ", ".")) for part in parts)
        or path.suffix.casefold() not in {".wem", ".bnk"}
    ):
        raise SystemExit(f"Percorso non sicuro nel payload: {name!r}")
    return relative


def _is_sellen_vanilla_wem(relative: str) -> bool:
    path = PurePosixPath(relative)
    return path.suffix.casefold() == ".wem" and path.stem == SELLEN_VANILLA_WEM_ID


def _verify_flat_payload(
    archive: zipfile.ZipFile,
    entries: list[tuple[str, zipfile.ZipInfo]],
) -> None:
    """Authenticate the direct patch_data/ tree using bounded streaming."""

    tree_digest = hashlib.sha256()
    wem_count = 0
    bnk_count = 0
    total_size = 0
    max_file_size = 0
    try:
        if len(entries) != PAYLOAD_FILE_COUNT:
            raise SystemExit(
                "Numero di file divergente in patch_data/: "
                f"attesi {PAYLOAD_FILE_COUNT}, ottenuti {len(entries)}"
            )
        expected_order = sorted(
            entries,
            key=lambda item: (
                unicodedata.normalize("NFC", item[0]).casefold(),
                item[0],
            ),
        )
        if entries != expected_order:
            raise SystemExit("Le voci di patch_data/ sono fuori dall'ordine canonico.")

        seen: set[str] = set()
        for relative, info in entries:
            checked_relative = _safe_payload_relative(f"patch_data/{relative}")
            if checked_relative != relative:
                raise SystemExit(f"Percorso divergente nel payload: {relative!r}")
            if _is_sellen_vanilla_wem(relative):
                raise SystemExit(
                    "Il WEM non verbale dell'animazione di Sellen deve restare vanilla."
                )
            canonical = unicodedata.normalize("NFC", relative).casefold()
            if canonical in seen:
                raise SystemExit(f"Nome duplicato in patch_data/: {relative!r}")
            seen.add(canonical)
            if info.file_size < 0 or info.file_size > PAYLOAD_MAX_FILE_SIZE:
                raise SystemExit(f"Membro non sicuro in patch_data/: {relative!r}")
            total_size += info.file_size
            if total_size > PAYLOAD_UNCOMPRESSED_SIZE:
                raise SystemExit("patch_data/ supera la dimensione autenticata.")
            max_file_size = max(max_file_size, info.file_size)
            if relative.casefold().endswith(".wem"):
                wem_count += 1
            else:
                bnk_count += 1

            encoded = relative.encode("utf-8")
            tree_digest.update(struct.pack("<I", len(encoded)))
            tree_digest.update(encoded)
            tree_digest.update(struct.pack("<Q", info.file_size))
            inflated = 0
            header = bytearray()
            with archive.open(info, "r") as member:
                while chunk := member.read(STREAM_CHUNK_SIZE):
                    inflated += len(chunk)
                    tree_digest.update(chunk)
                    if len(header) < 12:
                        header.extend(chunk[: 12 - len(header)])
            if inflated != info.file_size:
                raise SystemExit(f"Lettura incompleta nel payload: {relative!r}")
            if relative.casefold().endswith(".wem"):
                if (
                    len(header) < 12
                    or header[:4] != b"RIFF"
                    or header[8:12] != b"WAVE"
                ):
                    raise SystemExit(
                        f"Intestazione WEM non valida nel payload: {relative!r}"
                    )
            elif len(header) < 4 or header[:4] != b"BKHD":
                raise SystemExit(f"Intestazione BNK non valida nel payload: {relative!r}")
    except SystemExit:
        raise
    except (OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
        raise SystemExit("Errore di integrità, CRC o decompressione nel payload.") from exc

    if (
        wem_count != PAYLOAD_WEM_COUNT
        or bnk_count != PAYLOAD_BNK_COUNT
        or total_size != PAYLOAD_UNCOMPRESSED_SIZE
        or max_file_size != PAYLOAD_MAX_FILE_SIZE
    ):
        raise SystemExit(
            "Statistiche divergenti in patch_data/: "
            f"WEM={wem_count}, BNK={bnk_count}, byte={total_size}, "
            f"massimo={max_file_size}"
        )
    actual_tree = tree_digest.hexdigest()
    if actual_tree != PAYLOAD_TREE_SHA256:
        raise SystemExit(
            "SHA-256 dell'albero di patch_data/ divergente: "
            f"atteso {PAYLOAD_TREE_SHA256}, ottenuto {actual_tree}"
        )


def verify(path: str) -> None:
    archive_path = Path(path)
    if archive_path.name != FINAL_ARCHIVE_NAME:
        raise SystemExit(f"Nome obbligatorio dello ZIP finale: {FINAL_ARCHIVE_NAME}")
    try:
        metadata = archive_path.lstat()
    except OSError as exc:
        raise SystemExit(f"Release assente o illeggibile: {archive_path}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
        or bool(reparse_flag and file_attributes & reparse_flag)
    ):
        raise SystemExit("La release deve essere un file regolare, non un link.")
    if metadata.st_size > MAX_FINAL_ARCHIVE_SIZE:
        raise SystemExit("Il file ZIP supera il limite fisico della release.")

    with contextlib.ExitStack() as stack:
        try:
            archive_stream = stack.enter_context(archive_path.open("rb"))
        except OSError as exc:
            raise SystemExit(f"Release assente o illeggibile: {archive_path}") from exc
        opened = os.fstat(archive_stream.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_size > MAX_FINAL_ARCHIVE_SIZE
            or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
        ):
            raise SystemExit("La release è cambiata o supera il limite prima della lettura.")
        archive = stack.enter_context(zipfile.ZipFile(archive_stream, "r"))
        if archive.comment:
            raise SystemExit("Lo ZIP finale contiene un commento inatteso.")
        infos = archive.infolist()
        expected_member_count = len(EXPECTED_FILES) + PAYLOAD_FILE_COUNT
        if len(infos) != expected_member_count:
            raise SystemExit("Lo ZIP contiene una quantità inaspettata di membri.")
        names = [info.filename for info in infos]
        if not names or len(names) != len(set(names)):
            raise SystemExit("Lo ZIP è vuoto o contiene nomi duplicati.")
        canonical_names = {
            unicodedata.normalize("NFC", name).casefold() for name in names
        }
        if len(names) != len(canonical_names):
            raise SystemExit(
                "Lo ZIP contiene nomi duplicati per maiuscole o normalizzazione Unicode."
            )

        roots: set[str] = set()
        fixed_names: set[str] = set()
        relative_casefolds: set[str] = set()
        members: dict[str, zipfile.ZipInfo] = {}
        payload_entries: list[tuple[str, zipfile.ZipInfo]] = []
        total_uncompressed = 0
        total_compressed = 0
        payload_compressed = 0
        ordered_relatives: list[str] = []
        for info in infos:
            name = info.filename
            pure = PurePosixPath(name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in name
                or ":" in name
                or len(pure.parts) < 2
            ):
                raise SystemExit(f"Percorso non sicuro nella release: {name}")
            roots.add(pure.parts[0])
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            if unicodedata.normalize("NFC", relative) != relative:
                raise SystemExit(f"Nome non canonico nella release: {relative!r}")
            folded_relative = unicodedata.normalize("NFC", relative).casefold()
            if folded_relative in relative_casefolds:
                raise SystemExit(f"Destinazione relativa duplicata nella release: {relative}")
            relative_casefolds.add(folded_relative)
            ordered_relatives.append(relative)

            if info.flag_bits & 0x1:
                raise SystemExit(f"Membro cifrato proibito nella release: {name}")
            if info.compress_type != zipfile.ZIP_DEFLATED:
                raise SystemExit(f"Compressione inaspettata nella release: {name}")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if (
                info.date_time != ARCHIVE_TIMESTAMP
                or info.create_system != 3
                or unix_mode != (stat.S_IFREG | 0o644)
            ):
                raise SystemExit(f"Metadati non deterministici nella release: {name}")
            if info.is_dir():
                raise SystemExit(f"Directory esplicita proibita nella release: {name}")

            suffix = pure.suffix.casefold()
            if (
                suffix in FORBIDDEN_ARCHIVE_SUFFIXES
                and relative not in WHEEL_SHA256
            ):
                raise SystemExit(f"Archivio compresso annidato proibito: {name}")
            if suffix in FORBIDDEN_SUFFIXES:
                raise SystemExit(f"Binario/script proibito nella release: {name}")

            if relative.startswith("patch_data/"):
                payload_relative = _safe_payload_relative(relative)
                if info.file_size < 0 or info.file_size > PAYLOAD_MAX_FILE_SIZE:
                    raise SystemExit(f"Membro troppo grande nel payload: {name}")
                payload_compressed += info.compress_size
                if payload_compressed > MAX_PAYLOAD_COMPRESSED:
                    raise SystemExit("Il payload compresso supera il limite fisico.")
                payload_entries.append((payload_relative, info))
            else:
                fixed_names.add(relative)
                members[relative] = info
                if (
                    info.file_size < 0
                    or info.file_size > MAX_MEMBER_SIZE
                    or info.compress_size < 0
                    or info.compress_size > MAX_MEMBER_SIZE
                ):
                    raise SystemExit(f"Membro troppo grande nella release: {name}")
                total_uncompressed += info.file_size
                total_compressed += info.compress_size
                if (
                    total_uncompressed > MAX_TOTAL_UNCOMPRESSED
                    or total_compressed > MAX_TOTAL_COMPRESSED
                ):
                    raise SystemExit(
                        "La dimensione totale dichiarata della release supera il limite."
                    )

        if len(roots) != 1:
            raise SystemExit("Lo ZIP deve avere un'unica cartella radice.")
        root = next(iter(roots))
        expected_root = f"ERITA-{FINAL_VERSION}"
        if root != expected_root:
            raise SystemExit(f"Cartella radice inaspettata nella release: {root!r}")
        if fixed_names != EXPECTED_FILES:
            missing = sorted(EXPECTED_FILES - fixed_names)
            extra = sorted(fixed_names - EXPECTED_FILES)
            raise SystemExit(
                f"Allowlist della release divergente; mancanti={missing}, extra={extra}"
            )
        expected_order = sorted(EXPECTED_FILES) + [
            f"patch_data/{relative}" for relative, _info in payload_entries
        ]
        if ordered_relatives != expected_order:
            raise SystemExit("I membri della release sono fuori dall'ordine deterministico.")
        root_commands = sorted(
            relative
            for relative in fixed_names
            if "/" not in relative
            and PurePosixPath(relative).suffix.casefold() == ".cmd"
        )
        if root_commands != ["ERITA.cmd"]:
            raise SystemExit(
                "La release deve esporre solo ERITA.cmd nella cartella principale."
            )

        # Force decompression and CRC validation for every allowlisted member,
        # including documentation and the icon.  Keeping the bytes also avoids
        # parsing a different view if the archive is replaced during validation.
        try:
            member_bytes = {
                relative: archive.read(info)
                for relative, info in members.items()
            }
        except (OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
            raise SystemExit(
                "Errore di integrità, decompressione o CRC in un membro della release."
            ) from exc

        _verify_flat_payload(archive, payload_entries)

        for relative in SOURCE_FILES:
            if PurePosixPath(relative).suffix.casefold() not in {".py", ".cmd"}:
                continue
            try:
                source = member_bytes[relative].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SystemExit(f"Sorgente non UTF-8 nella release: {relative}") from exc
            folded_source = source.casefold()
            for pattern, label in FORBIDDEN_SOURCE_PATTERNS.items():
                if pattern in folded_source:
                    raise SystemExit(f"{label} trovato in {relative}: {pattern}")

        for relative, expected in WHEEL_SHA256.items():
            actual = _sha256(member_bytes[relative])
            if actual != expected:
                raise SystemExit(
                    f"SHA-256 errato per {relative}: atteso {expected}, ottenuto {actual}"
                )

        one_click = member_bytes["ERITA.cmd"].decode("utf-8")
        installer = member_bytes["interno/INSTALAR_AMBIENTE.cmd"].decode("utf-8")
        launcher = member_bytes["interno/ABRIR_INTERFACE.cmd"].decode("utf-8")
        required_installer_controls = (
            'for %%I in ("%~dp0..") do set "ERPT_PACKAGE_ROOT=%%~fI\\"',
            '"%ERPT_PY%" %ERPT_PY_SWITCH% -I -S -c',
            '"%ERPT_PY%" %ERPT_PY_SWITCH% -I -S -m venv --clear --copies',
            "sys.implementation.name == 'cpython'",
            "sys.version_info[:2] == (3,13)",
            "sys.version_info[2] >= 15",
            "sys.version_info.releaselevel == 'final'",
            "%LOCALAPPDATA%\\Programs\\Python\\Launcher\\py.exe",
            "%SystemRoot%\\py.exe",
            "%LOCALAPPDATA%\\Programs\\Python\\Python313\\python.exe",
            "%ERPT_PACKAGE_ROOT%wheelhouse",
            "%ERPT_PACKAGE_ROOT%patcher\\requirements-win64.lock",
            'Scripts\\python.exe" -I -S -c',
            "sys.prefix=sys.exec_prefix=sys.argv[1]",
            "runpy.run_module('pip',run_name='__main__')",
            "--no-index",
            "--require-hashes",
            "--only-binary=:all:",
        )
        missing_controls = [
            item for item in required_installer_controls if item not in installer
        ]
        if missing_controls:
            raise SystemExit(
                f"Controlli obbligatori assenti dall'installer: {missing_controls}"
            )
        if 'Scripts\\pythonw.exe" -I -S -c' not in launcher:
            raise SystemExit(
                "Il launcher non avvia Python senza l'elaborazione automatica del site."
            )
        if (
            "%LOCALAPPDATA%\\Programs\\Python\\Launcher\\py.exe" not in launcher
            or "%LOCALAPPDATA%\\Programs\\Python\\Python313\\python.exe"
            not in launcher
            or '"%ERPT_PY%" %ERPT_PY_SWITCH% -I -S -c' not in launcher
            or "sys.version_info[:2] != (3,13)" not in launcher
            or "sys.version_info[2] < 15" not in launcher
            or '"%ERPT_VENV%\\Scripts\\python.exe" -I -S -c' not in launcher
            or launcher.count("sys.version_info[:2] == (3,13)") < 3
            or 'call "%~dp0INSTALAR_AMBIENTE.cmd"' not in launcher
            or "if defined ERPTBR_INSTALL_ONLY exit /b 0" not in launcher
            or "import tkinter,customtkinter; from Crypto.Cipher import AES"
            not in launcher
            or "if defined ERPTBR_REPAIR_ATTEMPTED" not in launcher
            or "if not defined ERPTBR_INTERNAL_CALL" not in launcher
            or "if not defined ERPTBR_INTERNAL_CALL" not in installer
            or 'for %%I in ("%~dp0..") do set "ERPT_PACKAGE_ROOT=%%~fI\\"'
            not in launcher
        ):
            raise SystemExit(
                "Il launcher non convalida la compatibilità di Python e del venv."
            )

        required_one_click_controls = (
            "%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "%LOCALAPPDATA%\\Microsoft\\WindowsApps\\winget.exe",
            "%SystemRoot%\\System32\\curl.exe",
            'for /f "delims=" %%G in (\'%ERPT_POWERSHELL%',
            "https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe",
            "29452944",
            "EDEC09C4853AEAE9AC36EFB8C9F95B6B8E2FEE65EEE56D9767A8B7C69C574403",
            "CN=Python Software Foundation, O=Python Software Foundation, L=Beaverton, S=Oregon, C=US",
            "Microsoft.PowerShell.Utility\\Get-FileHash",
            "Microsoft.PowerShell.Security\\Get-AuthenticodeSignature -LiteralPath",
            "Modules\\Microsoft.PowerShell.Utility\\Microsoft.PowerShell.Utility.psd1",
            "Modules\\Microsoft.PowerShell.Security\\Microsoft.PowerShell.Security.psd1",
            "[IO.FileStream]::new",
            "[IO.FileOptions]::DeleteOnClose",
            "--exact --id Python.Python.3.13 --version 3.13.15 --source winget",
            "--scope user --architecture x64 --silent --disable-interactivity",
            "InstallAllUsers=0",
            "InstallLauncherAllUsers=0",
            "Include_freethreaded=0",
            "PrependPath=0",
            "AppendPath=0",
            'if not exist "%ERPT_WINGET%" goto :install_direct',
            "interno\\INSTALAR_AMBIENTE.cmd",
            "interno\\ABRIR_INTERFACE.cmd",
            "patcher\\bnk.py",
            "patcher\\diagnostics.py",
            'call "%~dp0interno\\ABRIR_INTERFACE.cmd"',
            "if defined ERPTBR_INSTALL_ONLY goto :success_install_only",
            "Local\\ERITA_Installer_",
            'set "ERPTBR_INTERNAL_CALL=1"',
            ":invalid_package",
            "ERITA-PACKAGE-001",
            "File obbligatorio mancante:",
            "Cartella obbligatoria mancante: patch_data",
            "usa prima Estrai tutto",
        )
        missing_one_click = [
            item for item in required_one_click_controls if item not in one_click
        ]
        if missing_one_click:
            raise SystemExit(
                "Controlli obbligatori assenti dall'installazione con un clic: "
                f"{missing_one_click}"
            )
        if one_click.count("goto :install_direct") != 1:
            raise SystemExit(
                "Il fallback diretto è raggiungibile solo quando WinGet è assente."
            )
        if "docs\\INCIDENTE-0.9.1.md" in one_click:
            raise SystemExit(
                "La documentazione informativa non può bloccare l'installazione."
            )
        for relative, expected in WHEEL_SHA256.items():
            bootstrap_relative = relative.replace("/", "\\")
            if bootstrap_relative not in one_click or expected not in one_click:
                raise SystemExit(
                    f"Il preflight del bootstrap non fissa nome/hash di {relative}."
                )
        preflight_order = (
            one_click.find("rem Rifiuta lo ZIP automatico"),
            one_click.find("call :find_python"),
            one_click.find('"%ERPT_WINGET%" install'),
        )
        if not (
            -1 not in preflight_order
            and preflight_order[0] < preflight_order[1] < preflight_order[2]
        ):
            raise SystemExit(
                "Il pacchetto deve essere autenticato prima di installare Python."
            )
        authentication_order = (
            one_click.find(
                "$hash=(Microsoft.PowerShell.Utility\\Get-FileHash -LiteralPath $path"
            ),
            one_click.find(
                "$signature=Microsoft.PowerShell.Security\\Get-AuthenticodeSignature "
                "-LiteralPath $path"
            ),
            one_click.find("$process=Start-Process -FilePath $path"),
        )
        if not (
            -1 not in authentication_order
            and authentication_order[0]
            < authentication_order[1]
            < authentication_order[2]
        ):
            raise SystemExit(
                "Hash e firma devono precedere l'esecuzione dell'installer ufficiale."
            )

        version = FINAL_VERSION.removeprefix("v")
        init_source = member_bytes["patcher/__init__.py"].decode("utf-8")
        gui_source = member_bytes["patcher/patcher_gui.py"].decode("utf-8")
        if f'__version__ = "{version}"' not in init_source or (
            f'PATCHER_VERSION = "{version}"' not in gui_source
        ):
            raise SystemExit("La versione della cartella radice diverge dal codice impacchettato.")
        _verify_gui_controls(gui_source)
        lock_source = member_bytes["patcher/requirements-win64.lock"].decode("utf-8")
        for expected in WHEEL_SHA256.values():
            if f"--hash=sha256:{expected}" not in lock_source:
                raise SystemExit(
                    f"Hash del wheel assente da requirements-win64.lock: {expected}"
                )

        try:
            final_opened = os.fstat(archive_stream.fileno())
            current = archive_path.lstat()
        except OSError as exc:
            raise SystemExit("La release è cambiata durante la convalida.") from exc
        current_attributes = getattr(current, "st_file_attributes", 0)
        if (
            not stat.S_ISREG(final_opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or final_opened.st_nlink != 1
            or current.st_nlink != 1
            or final_opened.st_size != metadata.st_size
            or current.st_size != metadata.st_size
            or (final_opened.st_dev, final_opened.st_ino)
            != (metadata.st_dev, metadata.st_ino)
            or (current.st_dev, current.st_ino) != (metadata.st_dev, metadata.st_ino)
            or stat.S_ISLNK(current.st_mode)
            or bool(reparse_flag and current_attributes & reparse_flag)
        ):
            raise SystemExit("La release è cambiata durante la convalida.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    verify(args.archive)
    print("ZIP finale verificato: sorgenti, wheel e patch_data/ autenticati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
