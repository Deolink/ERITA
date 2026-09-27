#!/usr/bin/env python3
"""Independently verify the final ERPT-BR Linux x86_64 tarball."""

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
        "ERPT-BR.sh",
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
EXECUTABLE_FILES = frozenset({"ERPT-BR.sh", "interno/INICIAR_LINUX.sh"})
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
FINAL_ARCHIVE_NAME = "ERPT-BR-v0.9.7-Linux-x86_64.tar.gz"
FINAL_PACKAGE_ROOT = "ERPT-BR-v0.9.7-Linux-x86_64"
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
    "curl": "download externo",
    "wget": "download externo",
    "http://": "download externo",
    "https://": "download externo",
    "apt-get": "gerenciador global de pacotes",
    "pacman": "gerenciador global de pacotes",
    "dnf ": "gerenciador global de pacotes",
    "yum ": "gerenciador global de pacotes",
    "zypper": "gerenciador global de pacotes",
    "eval ": "execucao dinamica de shell",
    "source ": "carregamento dinamico de shell",
    "rm -rf": "remocao recursiva forcada",
    "chmod 777": "permissao insegura",
    "chown ": "mudanca de proprietario",
    "taskkill": "controle de processo Windows",
    "pkill": "encerramento amplo de processos",
    "killall": "encerramento amplo de processos",
    "pyinstaller": "empacotador executavel",
    "nuitka": "empacotador executavel",
}


def _safe_relative(name: str, *, label: str) -> str:
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise SystemExit(f"Caminho inseguro em {label}: {name!r}")
    parts = name.split("/")
    pure = PurePosixPath(*parts)
    if (
        pure.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or pure.as_posix() != name
        or unicodedata.normalize("NFC", name) != name
        or any(part.endswith((" ", ".")) for part in parts)
    ):
        raise SystemExit(f"Caminho inseguro em {label}: {name!r}")
    return name


def _safe_payload_relative(relative: str) -> str:
    _safe_relative(relative, label="patch_data")
    if PurePosixPath(relative).suffix.casefold() not in {".wem", ".bnk"}:
        raise SystemExit(f"Extensao inesperada em patch_data/: {relative!r}")
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
        raise SystemExit(f"Link inseguro no runtime: {member_name!r} -> {link_name!r}")
    stack = list(PurePosixPath(member_name).parent.parts)
    for part in link_name.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            if len(stack) <= 1:
                raise SystemExit(
                    f"Link escapa de python/ no runtime: {member_name!r} -> {link_name!r}"
                )
            stack.pop()
        else:
            if part.endswith((" ", ".")):
                raise SystemExit(
                    f"Link inseguro no runtime: {member_name!r} -> {link_name!r}"
                )
            stack.append(part)
    if not stack or stack[0] != "python":
        raise SystemExit(
            f"Link escapa de python/ no runtime: {member_name!r} -> {link_name!r}"
        )
    return PurePosixPath(*stack).as_posix()


def _validate_runtime_tar(stream: BinaryIO) -> None:
    try:
        stream.seek(0)
        with tarfile.open(fileobj=stream, mode="r:gz") as archive:
            if archive.pax_headers:
                raise SystemExit("O runtime contem metadados PAX globais inesperados.")
            infos = archive.getmembers()
    except SystemExit:
        raise
    except (OSError, EOFError, tarfile.TarError) as exc:
        raise SystemExit("Runtime aninhado nao e um tar.gz integro.") from exc
    if not infos or len(infos) > RUNTIME_MAX_MEMBERS:
        raise SystemExit("Quantidade insegura de membros no runtime.")

    seen: set[str] = set()
    regular_names: set[str] = set()
    total_size = 0
    python_info: tarfile.TarInfo | None = None
    for info in infos:
        name = _safe_relative(info.name, label="runtime")
        if not name.startswith("python/"):
            raise SystemExit(f"Membro fora de python/ no runtime: {name!r}")
        normalized = unicodedata.normalize("NFC", name)
        if normalized in seen:
            raise SystemExit(f"Nome duplicado no runtime: {name!r}")
        # Linux paths are case-sensitive.  Astral's terminfo tree has valid
        # entries whose names differ only by case.
        seen.add(normalized)
        if info.pax_headers:
            raise SystemExit(f"Metadados PAX inesperados no runtime: {name!r}")
        if info.isreg():
            if info.size < 0 or info.size > RUNTIME_MAX_MEMBER_SIZE:
                raise SystemExit(f"Membro grande demais no runtime: {name!r}")
            total_size += info.size
            if total_size > RUNTIME_MAX_TOTAL_SIZE:
                raise SystemExit("Runtime excede o limite descompactado.")
            regular_names.add(name)
            if name == "python/bin/python3.13":
                python_info = info
        elif info.issym():
            _resolve_runtime_link(name, info.linkname)
        else:
            raise SystemExit(f"Tipo de membro proibido no runtime: {name!r}")

    if python_info is None or not (python_info.mode & 0o111):
        raise SystemExit("python/bin/python3.13 executavel ausente do runtime.")
    required = {"python/lib/libtcl9.0.so", "python/lib/libtcl9tk9.0.so"}
    if not required.issubset(regular_names):
        raise SystemExit("Bibliotecas Tcl/Tk obrigatorias ausentes do runtime.")
    if not any(
        name.startswith("python/lib/python3.13/lib-dynload/_tkinter")
        and name.endswith(".so")
        for name in regular_names
    ):
        raise SystemExit("Modulo _tkinter obrigatorio ausente do runtime.")


def _read_member(member: BinaryIO, expected_size: int, *, limit: int) -> bytes:
    if expected_size < 0 or expected_size > limit:
        raise SystemExit("Membro excede o limite de tamanho do release.")
    result = bytearray()
    while chunk := member.read(min(STREAM_CHUNK_SIZE, limit + 1 - len(result))):
        result.extend(chunk)
        if len(result) > limit:
            raise SystemExit("Membro excede o limite de tamanho do release.")
    if len(result) != expected_size:
        raise SystemExit("Leitura incompleta de membro do release.")
    return bytes(result)


def _hash_member(member: BinaryIO, expected_size: int, sink: BinaryIO | None = None) -> str:
    digest = hashlib.sha256()
    total = 0
    while chunk := member.read(STREAM_CHUNK_SIZE):
        total += len(chunk)
        if total > expected_size:
            raise SystemExit("Membro excedeu o tamanho declarado no release.")
        digest.update(chunk)
        if sink is not None:
            sink.write(chunk)
    if total != expected_size:
        raise SystemExit("Leitura incompleta de membro do release.")
    return digest.hexdigest()


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
        raise SystemExit(f"Controles obrigatorios ausentes da interface: {missing}")


def _verify_launchers(member_bytes: dict[str, bytes]) -> None:
    try:
        one_click = member_bytes["ERPT-BR.sh"].decode("utf-8")
        launcher = member_bytes["interno/INICIAR_LINUX.sh"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit("Launcher Linux nao e UTF-8.") from exc
    for relative, source in (
        ("ERPT-BR.sh", one_click),
        ("interno/INICIAR_LINUX.sh", launcher),
    ):
        if "\r" in source:
            raise SystemExit(f"Launcher Linux contem final de linha CRLF: {relative}")
        folded = source.casefold()
        for pattern, label in FORBIDDEN_LAUNCHER_PATTERNS.items():
            if pattern in folded:
                raise SystemExit(f"{label} encontrado em {relative}: {pattern}")
        if re.search(r"(?m)^\s*sudo\b", source):
            raise SystemExit(f"elevacao de privilegio encontrada em {relative}: sudo")

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
        raise SystemExit(f"Controles ausentes de ERPT-BR.sh: {missing}")

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
        'app_data="$data_base/ERPT-BR"',
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
        raise SystemExit(f"Controles ausentes de INICIAR_LINUX.sh: {missing}")
    for wheel, (_size, expected_hash) in WHEELS.items():
        name = PurePosixPath(wheel).name
        if name not in launcher or expected_hash not in launcher:
            raise SystemExit(f"Launcher nao autentica a wheel Linux: {name}")
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
        raise SystemExit("Runtime e wheels precisam ser autenticados antes do uso.")


def _verify_lock(member_bytes: dict[str, bytes]) -> None:
    try:
        lock = member_bytes["patcher/requirements-linux-x86_64.lock"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit("requirements Linux nao e UTF-8.") from exc
    if "\r" in lock or "win_amd64" in lock.casefold():
        raise SystemExit("requirements Linux contem dados Windows ou CRLF.")
    if "--only-binary=:all:" not in lock:
        raise SystemExit("requirements Linux nao exige wheels binarias.")
    for _relative, (_size, expected_hash) in WHEELS.items():
        if lock.count(f"--hash=sha256:{expected_hash}") != 1:
            raise SystemExit(f"Hash divergente ou duplicado no lock Linux: {expected_hash}")
    windows_hash = "c75b52aacc6c0c260f204cbdd834f76edc9fb0d8e0da9fbf8352ef58202564e2"
    if windows_hash in lock:
        raise SystemExit("Hash da wheel Windows apareceu no lock Linux.")


def verify(path: str | Path) -> None:
    archive_path = Path(path)
    if archive_path.name != FINAL_ARCHIVE_NAME:
        raise SystemExit(f"Nome obrigatorio do release Linux: {FINAL_ARCHIVE_NAME}")
    try:
        metadata = archive_path.lstat()
    except OSError as exc:
        raise SystemExit(f"Release ausente ou ilegivel: {archive_path}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_nlink != 1
        or bool(reparse_flag and attributes & reparse_flag)
    ):
        raise SystemExit("O release precisa ser um arquivo regular exclusivo.")
    if metadata.st_size <= 0 or metadata.st_size > MAX_FINAL_ARCHIVE_SIZE:
        raise SystemExit("O tar.gz excede o limite fisico do release.")

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
                raise SystemExit("O release mudou antes da validacao.")
            gzip_header = raw.read(10)
            if (
                len(gzip_header) != 10
                or gzip_header[:3] != b"\x1f\x8b\x08"
                or gzip_header[3] != 0
                or gzip_header[4:8] != b"\x00\x00\x00\x00"
            ):
                raise SystemExit("Cabecalho gzip nao e determinista.")
            raw.seek(0)
            try:
                with tarfile.open(fileobj=raw, mode="r|gz") as archive:
                    if archive.pax_headers:
                        raise SystemExit("O release contem metadados PAX globais.")
                    for info in archive:
                        name = _safe_relative(info.name, label="release")
                        folded = unicodedata.normalize("NFC", name).casefold()
                        if folded in canonical_names:
                            raise SystemExit(f"Nome duplicado no release: {name!r}")
                        canonical_names.add(folded)
                        if info.pax_headers:
                            raise SystemExit(f"Metadados PAX inesperados: {name!r}")
                        if (
                            info.uid != 0
                            or info.gid != 0
                            or info.uname != ""
                            or info.gname != ""
                            or info.mtime != ARCHIVE_MTIME
                        ):
                            raise SystemExit(f"Metadados nao deterministas: {name!r}")

                        if info.isdir():
                            if seen_file or info.mode != 0o755 or info.size != 0:
                                raise SystemExit(f"Diretorio fora da fase ou modo esperado: {name!r}")
                            directories.add(name)
                            ordered_directories.append(name)
                            continue
                        seen_file = True
                        if not info.isreg():
                            raise SystemExit(f"Tipo de membro proibido no release: {name!r}")
                        if not name.startswith(f"{FINAL_PACKAGE_ROOT}/"):
                            raise SystemExit(f"Arquivo fora da raiz unica: {name!r}")
                        relative = name[len(FINAL_PACKAGE_ROOT) + 1 :]
                        _safe_relative(relative, label="release")
                        if relative in files:
                            raise SystemExit(f"Arquivo duplicado no release: {relative!r}")
                        files.add(relative)
                        ordered_files.append(relative)
                        expected_mode = 0o755 if relative in EXECUTABLE_FILES else 0o644
                        if info.mode != expected_mode:
                            raise SystemExit(f"Modo inesperado no release: {relative!r}")
                        suffix = PurePosixPath(relative).suffix.casefold()
                        if suffix in WINDOWS_ONLY_SUFFIXES or "requirements-win64.lock" in relative.casefold():
                            raise SystemExit(f"Arquivo exclusivo do Windows no release: {relative!r}")
                        if suffix in ARCHIVE_SUFFIXES and relative != RUNTIME_RELATIVE:
                            raise SystemExit(f"Arquivo compactado aninhado proibido: {relative!r}")
                        member = archive.extractfile(info)
                        if member is None:
                            raise SystemExit(f"Membro regular ilegivel: {relative!r}")

                        if relative in SOURCE_FILES:
                            member_bytes[relative] = _read_member(
                                member, info.size, limit=MAX_SOURCE_SIZE
                            )
                        elif relative in WHEELS:
                            expected_size, _expected_hash = WHEELS[relative]
                            if info.size != expected_size:
                                raise SystemExit(f"Tamanho incorreto da wheel: {relative}")
                            wheel_digests[relative] = _hash_member(member, info.size)
                        elif relative == RUNTIME_RELATIVE:
                            if info.size != RUNTIME_ARCHIVE_SIZE:
                                raise SystemExit("Tamanho incorreto do runtime aninhado.")
                            runtime_digest = _hash_member(member, info.size, runtime_temp)
                        elif relative.startswith("patch_data/"):
                            payload_relative = _safe_payload_relative(
                                relative.removeprefix("patch_data/")
                            )
                            if _is_sellen_vanilla_wem(payload_relative):
                                raise SystemExit(
                                    "O WEM não verbal da animação da Sellen deve "
                                    "permanecer vanilla."
                                )
                            if info.size < 0 or info.size > PAYLOAD_MAX_FILE_SIZE:
                                raise SystemExit(f"Audio grande demais: {payload_relative!r}")
                            payload_count += 1
                            payload_total += info.size
                            payload_max = max(payload_max, info.size)
                            if payload_total > PAYLOAD_UNCOMPRESSED_SIZE:
                                raise SystemExit("patch_data/ excede o tamanho autenticado.")
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
                                    raise SystemExit("Audio excedeu o tamanho declarado.")
                                payload_tree.update(chunk)
                                if len(header) < 12:
                                    header.extend(chunk[: 12 - len(header)])
                            if read != info.size:
                                raise SystemExit(f"Audio truncado: {payload_relative!r}")
                            if payload_relative.casefold().endswith(".wem"):
                                valid_header = (
                                    len(header) >= 12
                                    and header[:4] == b"RIFF"
                                    and header[8:12] == b"WAVE"
                                )
                            else:
                                valid_header = len(header) >= 4 and header[:4] == b"BKHD"
                            if not valid_header:
                                raise SystemExit(f"Cabecalho de audio invalido: {payload_relative!r}")
                        else:
                            raise SystemExit(f"Arquivo fora da allowlist: {relative!r}")
            except SystemExit:
                raise
            except (OSError, EOFError, tarfile.TarError) as exc:
                raise SystemExit("Falha de integridade ou descompactacao do tar.gz.") from exc

            final_opened = os.fstat(raw.fileno())

        try:
            current = archive_path.lstat()
        except OSError as exc:
            raise SystemExit("O release mudou durante a validacao.") from exc
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
            raise SystemExit("O release mudou durante a validacao.")

        expected_fixed = SOURCE_FILES | frozenset(WHEELS) | {RUNTIME_RELATIVE}
        actual_fixed = files - {item for item in files if item.startswith("patch_data/")}
        if actual_fixed != expected_fixed:
            missing = sorted(expected_fixed - actual_fixed)
            extra = sorted(actual_fixed - expected_fixed)
            raise SystemExit(f"Allowlist divergente; ausentes={missing}, extras={extra}")
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
            raise SystemExit(f"Diretorios divergentes; ausentes={missing}, extras={extra}")
        if ordered_directories != sorted(expected_directories, key=_canonical_key):
            raise SystemExit("Diretorios fora da ordem determinista.")
        if ordered_files != sorted(files, key=_canonical_key):
            raise SystemExit("Arquivos fora da ordem determinista.")
        root_scripts = sorted(
            item
            for item in files
            if "/" not in item and PurePosixPath(item).suffix.casefold() == ".sh"
        )
        if root_scripts != ["ERPT-BR.sh"]:
            raise SystemExit("O pacote precisa expor somente ERPT-BR.sh na raiz.")

        if (
            payload_count != PAYLOAD_FILE_COUNT
            or payload_wem != PAYLOAD_WEM_COUNT
            or payload_bnk != PAYLOAD_BNK_COUNT
            or payload_total != PAYLOAD_UNCOMPRESSED_SIZE
            or payload_max != PAYLOAD_MAX_FILE_SIZE
        ):
            raise SystemExit(
                "Estatisticas divergentes em patch_data/: "
                f"WEM={payload_wem}, BNK={payload_bnk}, bytes={payload_total}, maior={payload_max}"
            )
        if payload_relatives != sorted(payload_relatives, key=_canonical_key):
            raise SystemExit("patch_data/ esta fora da ordem canonica.")
        if payload_tree.hexdigest() != PAYLOAD_TREE_SHA256:
            raise SystemExit("SHA-256 da arvore de patch_data/ divergiu.")

        if runtime_digest != RUNTIME_SHA256:
            raise SystemExit("SHA-256 incorreto do runtime aninhado.")
        _validate_runtime_tar(runtime_temp)
        for relative, (_size, expected_hash) in WHEELS.items():
            if wheel_digests.get(relative) != expected_hash:
                raise SystemExit(f"SHA-256 incorreto para {relative}")

        for relative in SOURCE_FILES:
            data = member_bytes.get(relative)
            if data is None:
                raise SystemExit(f"Fonte ausente no release: {relative}")
            if PurePosixPath(relative).suffix.casefold() in {".sh", ".py", ".md", ".lock"} or relative == "LICENSE":
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError as exc:
                    raise SystemExit(f"Fonte nao UTF-8: {relative}") from exc
                if "\r" in text:
                    raise SystemExit(f"Fonte textual sem LF canonico: {relative}")

        version = FINAL_VERSION.removeprefix("v")
        init_source = member_bytes["patcher/__init__.py"].decode("utf-8")
        gui_source = member_bytes["patcher/patcher_gui.py"].decode("utf-8")
        if f'__version__ = "{version}"' not in init_source:
            raise SystemExit("Versao divergente em patcher/__init__.py.")
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
    print("Release Linux verificado: fontes, runtime, wheels e patch_data/ autenticados.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
