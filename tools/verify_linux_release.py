#!/usr/bin/env python3
"""Independently verify the final ERITA Linux x86_64 tarball."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import stat
import struct
import tarfile
import tempfile
import unicodedata
from pathlib import Path, PurePosixPath
from typing import BinaryIO


SOURCE_FILES = frozenset(
    {
        "ERITA.sh",
        "interno/INICIAR_LINUX.sh",
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
        "patcher/requirements-linux-x86_64.lock",
    }
)
EXECUTABLE_FILES = frozenset({"ERITA.sh", "interno/INICIAR_LINUX.sh"})
WHEELS = {
    "wheelhouse/customtkinter-5.2.2-py3-none-any.whl": (
        296_062,
        "14ad3e7cd3cb3b9eb642b9d4e8711ae80d3f79fb82545ad11258eeffb2e6b37c",
    ),
    "wheelhouse/darkdetect-0.8.0-py3-none-any.whl": (
        8_955,
        "a7509ccf517eaad92b31c214f593dbcf138ea8a43b2935406bbd565e15527a85",
    ),
    "wheelhouse/packaging-26.3-py3-none-any.whl": (
        129_956,
        "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c",
    ),
    "wheelhouse/pycryptodome-3.23.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl": (
        2_268_954,
        "c8987bd3307a39bc03df5c8e0e3d8be0c4c3518b7f044b0f4c15d1aa78f52575",
    ),
}

FINAL_VERSION = "v0.9.7"
FINAL_ARCHIVE_NAME = "ERITA-v0.9.7-Linux-x86_64.tar.gz"
FINAL_PACKAGE_ROOT = "ERITA-v0.9.7-Linux-x86_64"
RUNTIME_ARCHIVE_NAME = (
    "cpython-3.13.15+20260924-x86_64-unknown-linux-gnu-"
    "install_only_stripped.tar.gz"
)
RUNTIME_RELATIVE = f"runtime/{RUNTIME_ARCHIVE_NAME}"
RUNTIME_ARCHIVE_SIZE = 34_993_852
RUNTIME_SHA256 = "d0b640eed27fbdd6f5f2bd33444aee53df2c8863f8b2a96f4094717411e3de9c"
RUNTIME_MAX_MEMBERS = 10_000
RUNTIME_MAX_TOTAL_SIZE = 256 * 1024 * 1024
RUNTIME_MAX_MEMBER_SIZE = 64 * 1024 * 1024

PAYLOAD_TREE_SHA256 = "e97467e8ebbd1da87be96a44e4a2ee5694cd41c0bf592159b0570258d0b8460e"
PAYLOAD_FILE_COUNT = 9_240
PAYLOAD_WEM_COUNT = 8_968
PAYLOAD_BNK_COUNT = 272
PAYLOAD_UNCOMPRESSED_SIZE = 605_607_009
PAYLOAD_MAX_FILE_SIZE = 74_956_066
SELLEN_VANILLA_WEM_ID = "553755359"

ARCHIVE_MTIME = 1_577_836_800
STREAM_CHUNK_SIZE = 1024 * 1024
MAX_SOURCE_SIZE = 5 * 1024 * 1024
MAX_FINAL_ARCHIVE_SIZE = (
    PAYLOAD_UNCOMPRESSED_SIZE
    + RUNTIME_ARCHIVE_SIZE
    + sum(size for size, _digest in WHEELS.values())
    + 64 * 1024 * 1024
)
WINDOWS_ONLY_SUFFIXES = frozenset(
    {".bat", ".cmd", ".com", ".dll", ".exe", ".ps1", ".pyd", ".scr"}
)
ARCHIVE_SUFFIXES = frozenset(
    {".7z", ".bz2", ".cab", ".gz", ".iso", ".rar", ".tar", ".tgz", ".xz", ".zip"}
)
FORBIDDEN_LAUNCHER_PATTERNS = {
    "curl": "download esterno",
    "wget": "download esterno",
    "http://": "download esterno",
    "https://": "download esterno",
    "apt-get": "gestore globale dei pacchetti",
    "pacman": "gestore globale dei pacchetti",
    "dnf ": "gestore globale dei pacchetti",
    "yum ": "gestore globale dei pacchetti",
    "zypper": "gestore globale dei pacchetti",
    "eval ": "esecuzione dinamica della shell",
    "source ": "caricamento dinamico della shell",
    "rm -rf": "rimozione ricorsiva forzata",
    "chmod 777": "permesso non sicuro",
    "chown ": "cambio di proprietario",
    "taskkill": "controllo dei processi di Windows",
    "pkill": "terminazione estesa di processi",
    "killall": "terminazione estesa di processi",
    "pyinstaller": "impacchettatore eseguibile",
    "nuitka": "impacchettatore eseguibile",
}
# Solo ERITA: come FORBIDDEN_SOURCE_PATTERNS in verify_source_release.py, il bypass
# di sviluppo del pin del payload non deve mai arrivare in una release Linux.
FORBIDDEN_SOURCE_PATTERNS = {
    "erita_dev_unsafe_skip_payload_pin": "bypass di sviluppo della convalida del payload",
}


def _safe_relative(name: str, *, label: str) -> str:
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise SystemExit(f"Percorso non sicuro in {label}: {name!r}")
    parts = name.split("/")
    pure = PurePosixPath(*parts)
    if (
        pure.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or pure.as_posix() != name
        or unicodedata.normalize("NFC", name) != name
        or any(part.endswith((" ", ".")) for part in parts)
    ):
        raise SystemExit(f"Percorso non sicuro in {label}: {name!r}")
    return name


def _safe_payload_relative(relative: str) -> str:
    _safe_relative(relative, label="patch_data")
    if PurePosixPath(relative).suffix.casefold() not in {".wem", ".bnk"}:
        raise SystemExit(f"Estensione inattesa in patch_data/: {relative!r}")
    return relative


def _is_sellen_vanilla_wem(relative: str) -> bool:
    path = PurePosixPath(relative)
    return path.suffix.casefold() == ".wem" and path.stem == SELLEN_VANILLA_WEM_ID


def _canonical_key(name: str) -> tuple[str, str]:
    return (unicodedata.normalize("NFC", name).casefold(), name)


def _resolve_runtime_link(member_name: str, link_name: str) -> str:
    if (
        not link_name
        or link_name.startswith("/")
        or "\\" in link_name
        or ":" in link_name
        or "\x00" in link_name
        or unicodedata.normalize("NFC", link_name) != link_name
    ):
        raise SystemExit(f"Link non sicuro nel runtime: {member_name!r} -> {link_name!r}")
    stack = list(PurePosixPath(member_name).parent.parts)
    for part in link_name.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if len(stack) <= 1:
                raise SystemExit(
                    f"Il link esce da python/ nel runtime: {member_name!r} -> {link_name!r}"
                )
            stack.pop()
        else:
            if part.endswith((" ", ".")):
                raise SystemExit(
                    f"Link non sicuro nel runtime: {member_name!r} -> {link_name!r}"
                )
            stack.append(part)
    if not stack or stack[0] != "python":
        raise SystemExit(
            f"Il link esce da python/ nel runtime: {member_name!r} -> {link_name!r}"
        )
    return PurePosixPath(*stack).as_posix()


def _validate_runtime_tar(stream: BinaryIO) -> None:
    try:
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode="r:gz") as archive:
            if archive.pax_headers:
                raise SystemExit("Il runtime contiene metadati PAX globali inattesi.")
            infos = archive.getmembers()
    except SystemExit:
        raise
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise SystemExit("Il runtime annidato non è un tar.gz integro.") from exc
    if not infos or len(infos) > RUNTIME_MAX_MEMBERS:
        raise SystemExit("Numero non sicuro di membri nel runtime.")

    seen: set[str] = set()
    regular_names: set[str] = set()
    total_size = 0
    python_info: tarfile.TarInfo | None = None
    for info in infos:
        name = _safe_relative(info.name, label="runtime")
        if not name.startswith("python/"):
            raise SystemExit(f"Membro fuori da python/ nel runtime: {name!r}")
        normalized = unicodedata.normalize("NFC", name)
        if normalized in seen:
            raise SystemExit(f"Nome duplicato nel runtime: {name!r}")
        # Linux paths are case-sensitive.  Astral's terminfo tree has valid
        # entries whose names differ only by case.
        seen.add(normalized)
        if info.pax_headers:
            raise SystemExit(f"Metadati PAX inattesi nel runtime: {name!r}")
        if info.isreg():
            if info.size < 0 or info.size > RUNTIME_MAX_MEMBER_SIZE:
                raise SystemExit(f"Membro troppo grande nel runtime: {name!r}")
            total_size += info.size
            if total_size > RUNTIME_MAX_TOTAL_SIZE:
                raise SystemExit("Il runtime supera il limite decompresso.")
            regular_names.add(name)
            if name == "python/bin/python3.13":
                python_info = info
        elif info.issym():
            _resolve_runtime_link(name, info.linkname)
        else:
            raise SystemExit(f"Tipo di membro proibito nel runtime: {name!r}")

    if python_info is None or not (python_info.mode & 0o111):
        raise SystemExit("python/bin/python3.13 eseguibile mancante nel runtime.")
    required = {"python/lib/libtcl9.0.so", "python/lib/libtcl9tk9.0.so"}
    if not required.issubset(regular_names):
        raise SystemExit("Librerie Tcl/Tk obbligatorie mancanti nel runtime.")
    if not any(
        name.startswith("python/lib/python3.13/lib-dynload/_tkinter")
        and name.endswith(".so")
        for name in regular_names
    ):
        raise SystemExit("Modulo _tkinter obbligatorio mancante nel runtime.")


def _read_member(member: BinaryIO, expected_size: int, *, limit: int) -> bytes:
    if expected_size < 0 or expected_size > limit:
        raise SystemExit("Il membro supera il limite di dimensione della release.")
    result = bytearray()
    while chunk := member.read(min(STREAM_CHUNK_SIZE, limit + 1 - len(result))):
        result.extend(chunk)
        if len(result) > limit:
            raise SystemExit("Il membro supera il limite di dimensione della release.")
    if len(result) != expected_size:
        raise SystemExit("Lettura incompleta di un membro della release.")
    return bytes(result)


def _hash_member(member: BinaryIO, expected_size: int, sink: BinaryIO | None = None) -> str:
    digest = hashlib.sha256()
    total = 0
    while chunk := member.read(STREAM_CHUNK_SIZE):
        total += len(chunk)
        if total > expected_size:
            raise SystemExit("Il membro ha superato la dimensione dichiarata nella release.")
        digest.update(chunk)
        if sink is not None:
            sink.write(chunk)
    if total != expected_size:
        raise SystemExit("Lettura incompleta di un membro della release.")
    return digest.hexdigest()


def _verify_source_patterns(relative: str, source: str) -> None:
    folded = source.casefold()
    for pattern, label in FORBIDDEN_SOURCE_PATTERNS.items():
        if pattern in folded:
            raise SystemExit(f"{label} trovato in {relative}: {pattern}")


def _verify_gui_controls(gui_source: str) -> None:
    version = FINAL_VERSION.removeprefix("v")
    required = (
        f'PATCHER_VERSION = "{version}"',
        "INSTALLATION_SUSPENDED = False",
        "BHD_INTEGRITY_SCOPED_MOD",
        "bhd_integrity_mode=BHD_INTEGRITY_SCOPED_MOD",
        '"easyanticheat_eos.exe": "Easy Anti-Cheat EOS"',
    )
    missing = [item for item in required if item not in gui_source]
    if missing:
        raise SystemExit(f"Controlli obbligatori assenti dall'interfaccia: {missing}")


def _verify_launchers(member_bytes: dict[str, bytes]) -> None:
    try:
        one_click = member_bytes["ERITA.sh"].decode("utf-8")
        launcher = member_bytes["interno/INICIAR_LINUX.sh"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit("Il launcher Linux non è UTF-8.") from exc
    for relative, source in (
        ("ERITA.sh", one_click),
        ("interno/INICIAR_LINUX.sh", launcher),
    ):
        if "\r" in source:
            raise SystemExit(f"Il launcher Linux contiene fine riga CRLF: {relative}")
        folded = source.casefold()
        for pattern, label in FORBIDDEN_LAUNCHER_PATTERNS.items():
            if pattern in folded:
                raise SystemExit(f"{label} trovato in {relative}: {pattern}")
        if re.search(r"(?m)^\s*sudo\b", source):
            raise SystemExit(f"elevazione di privilegi trovata in {relative}: sudo")

    required_one_click = (
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "umask 077",
        '[[ "$(uname -s)" == "Linux" ]]',
        "x86_64|amd64",
        "(( EUID != 0 ))",
        '[[ ! -L "$launcher" ]]',
        'internal="$package_root/interno/INICIAR_LINUX.sh"',
        "export ERPTBR_INTERNAL_CALL=1",
        'exec /usr/bin/env bash "$internal" "$package_root"',
    )
    missing = [item for item in required_one_click if item not in one_click]
    if missing:
        raise SystemExit(f"Controlli assenti da ERITA.sh: {missing}")

    required_launcher = (
        "#!/usr/bin/env bash",
        "set -Eeuo pipefail",
        "umask 077",
        f'readonly APP_VERSION="{FINAL_VERSION.removeprefix("v")}"',
        f'readonly RUNTIME_NAME="{RUNTIME_ARCHIVE_NAME}"',
        f'readonly RUNTIME_SIZE="{RUNTIME_ARCHIVE_SIZE}"',
        f'readonly RUNTIME_SHA256="{RUNTIME_SHA256}"',
        '[[ "${ERPTBR_INTERNAL_CALL:-}" == "1" ]]',
        '[[ -n "${HOME:-}" && "$HOME" == /* ]]',
        "sha256sum stat tar flock mktemp mv mkdir find date rmdir",
        'runtime_archive="$package_root/runtime/$RUNTIME_NAME"',
        'requirements="$package_root/patcher/requirements-linux-x86_64.lock"',
        'data_base=${XDG_DATA_HOME:-"$HOME/.local/share"}',
        'app_data="$data_base/ERITA"',
        "flock -n 9",
        "tar --extract --gzip --file \"$runtime_archive\"",
        "--no-same-owner --no-same-permissions",
        "sys.version_info[:3] == (3,13,15)",
        "sysconfig.get_platform() == 'linux-x86_64'",
        "not sysconfig.get_config_var('Py_GIL_DISABLED')",
        '"$runtime_python" -I -m pip --isolated install',
        "--disable-pip-version-check --no-input --no-index",
        "--require-hashes",
        "--only-binary=:all:",
        "find \"$deps_staging\" -type l",
        'export ERPTBR_PACKAGE_KIND="linux-portable-tar"',
        '[[ "${ERPTBR_INSTALL_ONLY:-}" == "1" ]]',
        'exec "$runtime_python" -I -S -c',
        "runpy.run_module('patcher.patcher_gui',run_name='__main__')",
    )
    missing = [item for item in required_launcher if item not in launcher]
    if missing:
        raise SystemExit(f"Controlli assenti da INICIAR_LINUX.sh: {missing}")
    for wheel, (_size, expected_hash) in WHEELS.items():
        name = PurePosixPath(wheel).name
        if name not in launcher or expected_hash not in launcher:
            raise SystemExit(f"Il launcher non autentica la wheel Linux: {name}")
    authentication_order = (
        launcher.find("actual_runtime_hash=$(sha256_file"),
        launcher.find("tar --extract --gzip --file"),
        launcher.find('actual=$(sha256_file "$wheel_path")'),
        launcher.find('"$runtime_python" -I -m pip --isolated install'),
    )
    if (
        -1 in authentication_order
        or authentication_order[0] >= authentication_order[1]
        or authentication_order[2] >= authentication_order[3]
    ):
        raise SystemExit("Runtime e wheel devono essere autenticati prima dell'uso.")


def _verify_lock(member_bytes: dict[str, bytes]) -> None:
    try:
        lock = member_bytes["patcher/requirements-linux-x86_64.lock"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit("requirements Linux non è UTF-8.") from exc
    if "\r" in lock or "win_amd64" in lock.casefold():
        raise SystemExit("requirements Linux contiene dati Windows o CRLF.")
    if "--only-binary=:all:" not in lock:
        raise SystemExit("requirements Linux non richiede wheel binarie.")
    for _relative, (_size, expected_hash) in WHEELS.items():
        if lock.count(f"--hash=sha256:{expected_hash}") != 1:
            raise SystemExit(f"Hash divergente o duplicato nel lock Linux: {expected_hash}")
    windows_hash = "c75b52aacc6c0c260f204cbdd834f76edc9fb0d8e0da9fbf8352ef58202564e2"
    if windows_hash in lock:
        raise SystemExit("L'hash della wheel Windows è comparso nel lock Linux.")


def verify(path: str | Path) -> None:
    archive_path = Path(path)
    if archive_path.name != FINAL_ARCHIVE_NAME:
        raise SystemExit(f"Nome obbligatorio della release Linux: {FINAL_ARCHIVE_NAME}")
    try:
        metadata = archive_path.lstat()
    except OSError as exc:
        raise SystemExit(f"Release mancante o illeggibile: {archive_path}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
        or bool(reparse_flag and attributes & reparse_flag)
    ):
        raise SystemExit("La release deve essere un file regolare esclusivo.")
    if metadata.st_size <= 0 or metadata.st_size > MAX_FINAL_ARCHIVE_SIZE:
        raise SystemExit("Il tar.gz supera il limite fisico della release.")

    member_bytes: dict[str, bytes] = {}
    wheel_digests: dict[str, str] = {}
    runtime_temp = tempfile.TemporaryFile()
    runtime_digest = ""
    directories: set[str] = set()
    files: set[str] = set()
    ordered_directories: list[str] = []
    ordered_files: list[str] = []
    canonical_names: set[str] = set()
    payload_tree = hashlib.sha256()
    payload_count = payload_wem = payload_bnk = payload_total = payload_max = 0
    payload_relatives: list[str] = []
    seen_file = False

    try:
        with archive_path.open("rb") as raw:
            opened = os.fstat(raw.fileno())
            if (
                opened.st_nlink != 1
                or (opened.st_dev, opened.st_ino, opened.st_size)
                != (metadata.st_dev, metadata.st_ino, metadata.st_size)
            ):
                raise SystemExit("La release è cambiata prima della convalida.")
            gzip_header = raw.read(10)
            if (
                len(gzip_header) != 10
                or gzip_header[:3] != b"\x1f\x8b\x08"
                or gzip_header[3] != 0
                or gzip_header[4:8] != b"\x00\x00\x00\x00"
            ):
                raise SystemExit("L'intestazione gzip non è deterministica.")
            raw.seek(0)
            try:
                with tarfile.open(fileobj=raw, mode="r|gz") as archive:
                    if archive.pax_headers:
                        raise SystemExit("La release contiene metadati PAX globali.")
                    for info in archive:
                        name = _safe_relative(info.name, label="release")
                        folded = unicodedata.normalize("NFC", name).casefold()
                        if folded in canonical_names:
                            raise SystemExit(f"Nome duplicato nella release: {name!r}")
                        canonical_names.add(folded)
                        if info.pax_headers:
                            raise SystemExit(f"Metadati PAX inattesi: {name!r}")
                        if (
                            info.uid != 0
                            or info.gid != 0
                            or info.uname != ""
                            or info.gname != ""
                            or info.mtime != ARCHIVE_MTIME
                        ):
                            raise SystemExit(f"Metadati non deterministici: {name!r}")

                        if info.isdir():
                            if seen_file or info.mode != 0o755 or info.size != 0:
                                raise SystemExit(f"Directory fuori dalla fase o dal modo atteso: {name!r}")
                            directories.add(name)
                            ordered_directories.append(name)
                            continue
                        seen_file = True
                        if not info.isreg():
                            raise SystemExit(f"Tipo di membro proibito nella release: {name!r}")
                        if not name.startswith(f"{FINAL_PACKAGE_ROOT}/"):
                            raise SystemExit(f"File fuori dall'unica radice: {name!r}")
                        relative = name[len(FINAL_PACKAGE_ROOT) + 1 :]
                        _safe_relative(relative, label="release")
                        if relative in files:
                            raise SystemExit(f"File duplicato nella release: {relative!r}")
                        files.add(relative)
                        ordered_files.append(relative)
                        expected_mode = 0o755 if relative in EXECUTABLE_FILES else 0o644
                        if info.mode != expected_mode:
                            raise SystemExit(f"Modo inatteso nella release: {relative!r}")
                        suffix = PurePosixPath(relative).suffix.casefold()
                        if suffix in WINDOWS_ONLY_SUFFIXES or "requirements-win64.lock" in relative.casefold():
                            raise SystemExit(f"File solo per Windows nella release: {relative!r}")
                        if suffix in ARCHIVE_SUFFIXES and relative != RUNTIME_RELATIVE:
                            raise SystemExit(f"Archivio compresso annidato proibito: {relative!r}")
                        member = archive.extractfile(info)
                        if member is None:
                            raise SystemExit(f"Membro regolare illeggibile: {relative!r}")

                        if relative in SOURCE_FILES:
                            member_bytes[relative] = _read_member(
                                member, info.size, limit=MAX_SOURCE_SIZE
                            )
                        elif relative in WHEELS:
                            expected_size, _expected_hash = WHEELS[relative]
                            if info.size != expected_size:
                                raise SystemExit(f"Dimensione della wheel errata: {relative}")
                            wheel_digests[relative] = _hash_member(member, info.size)
                        elif relative == RUNTIME_RELATIVE:
                            if info.size != RUNTIME_ARCHIVE_SIZE:
                                raise SystemExit("Dimensione del runtime annidato errata.")
                            runtime_digest = _hash_member(member, info.size, runtime_temp)
                        elif relative.startswith("patch_data/"):
                            payload_relative = _safe_payload_relative(
                                relative.removeprefix("patch_data/")
                            )
                            if _is_sellen_vanilla_wem(payload_relative):
                                raise SystemExit(
                                    "Il WEM non verbale dell'animazione di Sellen deve "
                                    "restare vanilla."
                                )
                            if info.size < 0 or info.size > PAYLOAD_MAX_FILE_SIZE:
                                raise SystemExit(f"Audio troppo grande: {payload_relative!r}")
                            payload_count += 1
                            payload_total += info.size
                            payload_max = max(payload_max, info.size)
                            if payload_total > PAYLOAD_UNCOMPRESSED_SIZE:
                                raise SystemExit("patch_data/ supera la dimensione autenticata.")
                            if payload_relative.casefold().endswith(".wem"):
                                payload_wem += 1
                            else:
                                payload_bnk += 1
                            payload_relatives.append(payload_relative)
                            encoded = payload_relative.encode("utf-8")
                            payload_tree.update(struct.pack("<I", len(encoded)))
                            payload_tree.update(encoded)
                            payload_tree.update(struct.pack("<Q", info.size))
                            read = 0
                            header = bytearray()
                            while chunk := member.read(STREAM_CHUNK_SIZE):
                                read += len(chunk)
                                if read > info.size:
                                    raise SystemExit("L'audio ha superato la dimensione dichiarata.")
                                payload_tree.update(chunk)
                                if len(header) < 12:
                                    header.extend(chunk[: 12 - len(header)])
                            if read != info.size:
                                raise SystemExit(f"Audio troncato: {payload_relative!r}")
                            if payload_relative.casefold().endswith(".wem"):
                                valid_header = (
                                    len(header) >= 12
                                    and header[:4] == b"RIFF"
                                    and header[8:12] == b"WAVE"
                                )
                            else:
                                valid_header = len(header) >= 4 and header[:4] == b"BKHD"
                            if not valid_header:
                                raise SystemExit(f"Intestazione audio non valida: {payload_relative!r}")
                        else:
                            raise SystemExit(f"File fuori dalla allowlist: {relative!r}")
            except SystemExit:
                raise
            except (OSError, EOFError, tarfile.TarError) as exc:
                raise SystemExit("Errore di integrità o decompressione del tar.gz.") from exc

            final_opened = os.fstat(raw.fileno())

        try:
            current = archive_path.lstat()
        except OSError as exc:
            raise SystemExit("La release è cambiata durante la convalida.") from exc
        current_attributes = getattr(current, "st_file_attributes", 0)
        if (
            not stat.S_ISREG(final_opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or final_opened.st_nlink != 1
            or current.st_nlink != 1
            or (final_opened.st_dev, final_opened.st_ino, final_opened.st_size)
            != (metadata.st_dev, metadata.st_ino, metadata.st_size)
            or (current.st_dev, current.st_ino, current.st_size)
            != (metadata.st_dev, metadata.st_ino, metadata.st_size)
            or stat.S_ISLNK(current.st_mode)
            or bool(reparse_flag and current_attributes & reparse_flag)
        ):
            raise SystemExit("La release è cambiata durante la convalida.")

        expected_fixed = SOURCE_FILES | frozenset(WHEELS) | {RUNTIME_RELATIVE}
        actual_fixed = files - {item for item in files if item.startswith("patch_data/")}
        if actual_fixed != expected_fixed:
            missing = sorted(expected_fixed - actual_fixed)
            extra = sorted(actual_fixed - expected_fixed)
            raise SystemExit(f"Allowlist divergente; mancanti={missing}, in più={extra}")
        expected_directories = {FINAL_PACKAGE_ROOT}
        for relative in files:
            parts = PurePosixPath(relative).parts
            for index in range(1, len(parts)):
                expected_directories.add(
                    f"{FINAL_PACKAGE_ROOT}/{PurePosixPath(*parts[:index]).as_posix()}"
                )
        if directories != expected_directories:
            missing = sorted(expected_directories - directories)
            extra = sorted(directories - expected_directories)
            raise SystemExit(f"Directory divergenti; mancanti={missing}, in più={extra}")
        if ordered_directories != sorted(expected_directories, key=_canonical_key):
            raise SystemExit("Directory fuori dall'ordine deterministico.")
        if ordered_files != sorted(files, key=_canonical_key):
            raise SystemExit("File fuori dall'ordine deterministico.")
        root_scripts = sorted(
            item
            for item in files
            if "/" not in item and PurePosixPath(item).suffix.casefold() == ".sh"
        )
        if root_scripts != ["ERITA.sh"]:
            raise SystemExit("Il pacchetto deve esporre solo ERITA.sh nella radice.")

        if (
            payload_count != PAYLOAD_FILE_COUNT
            or payload_wem != PAYLOAD_WEM_COUNT
            or payload_bnk != PAYLOAD_BNK_COUNT
            or payload_total != PAYLOAD_UNCOMPRESSED_SIZE
            or payload_max != PAYLOAD_MAX_FILE_SIZE
        ):
            raise SystemExit(
                "Statistiche divergenti in patch_data/: "
                f"WEM={payload_wem}, BNK={payload_bnk}, byte={payload_total}, massimo={payload_max}"
            )
        if payload_relatives != sorted(payload_relatives, key=_canonical_key):
            raise SystemExit("patch_data/ è fuori dall'ordine canonico.")
        if payload_tree.hexdigest() != PAYLOAD_TREE_SHA256:
            raise SystemExit("SHA-256 dell'albero di patch_data/ divergente.")

        if runtime_digest != RUNTIME_SHA256:
            raise SystemExit("SHA-256 del runtime annidato errato.")
        _validate_runtime_tar(runtime_temp)
        for relative, (_size, expected_hash) in WHEELS.items():
            if wheel_digests.get(relative) != expected_hash:
                raise SystemExit(f"SHA-256 errato per {relative}")

        for relative in SOURCE_FILES:
            data = member_bytes.get(relative)
            if data is None:
                raise SystemExit(f"Sorgente mancante nella release: {relative}")
            if PurePosixPath(relative).suffix.casefold() in {".sh", ".py", ".md", ".lock"} or relative == "LICENSE":
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise SystemExit(f"Sorgente non UTF-8: {relative}") from exc
                if "\r" in text:
                    raise SystemExit(f"Sorgente testuale senza LF canonico: {relative}")
                if relative.endswith(".py"):
                    _verify_source_patterns(relative, text)

        version = FINAL_VERSION.removeprefix("v")
        init_source = member_bytes["patcher/__init__.py"].decode("utf-8")
        gui_source = member_bytes["patcher/patcher_gui.py"].decode("utf-8")
        if f'__version__ = "{version}"' not in init_source:
            raise SystemExit("Versione divergente in patcher/__init__.py.")
        _verify_gui_controls(gui_source)
        _verify_launchers(member_bytes)
        _verify_lock(member_bytes)
    finally:
        runtime_temp.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    verify(args.archive)
    print("Release Linux verificata: sorgenti, runtime, wheel e patch_data/ autenticati.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
