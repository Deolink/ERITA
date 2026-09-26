#!/usr/bin/env python3
"""Build the authenticated, portable Linux x86_64 ERPT-BR release."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import os
import re
import stat
import struct
import tarfile
import unicodedata
import uuid
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Sequence


SOURCE_FILES = (
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
)
EXECUTABLE_FILES = frozenset({"ERPT-BR.sh", "interno/INICIAR_LINUX.sh"})
TEXT_SUFFIXES = frozenset({".sh", ".lock", ".md", ".py"})

# Each value is (byte size, SHA-256).  Keeping the size fixed catches a damaged
# wheel before hashing and makes the release verifier's resource limits exact.
WHEELS = {
    "customtkinter-5.2.2-py3-none-any.whl": (
        296_062,
        "14ad3e7cd3cb3b9eb642b9d4e8711ae80d3f79fb82545ad11258eeffb2e6b37c",
    ),
    "darkdetect-0.8.0-py3-none-any.whl": (
        8_955,
        "a7509ccf517eaad92b31c214f593dbcf138ea8a43b2935406bbd565e15527a85",
    ),
    "packaging-26.3-py3-none-any.whl": (
        129_956,
        "d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c",
    ),
    "pycryptodome-3.23.0-cp37-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl": (
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
RUNTIME_ARCHIVE_SIZE = 34_993_852
RUNTIME_SHA256 = "d0b640eed27fbdd6f5f2bd33444aee53df2c8863f8b2a96f4094717411e3de9c"
RUNTIME_MAX_MEMBERS = 10_000
RUNTIME_MAX_TOTAL_SIZE = 256 * 1024 * 1024
RUNTIME_MAX_MEMBER_SIZE = 64 * 1024 * 1024

# The ZIP is only an authenticated build input.  Its audio members are written
# directly below patch_data/ in the public tarball.
PAYLOAD_ARCHIVE_SIZE = 588_468_447
PAYLOAD_SHA256 = "430e9693a9b3313826e9f7c890cf592eb5b468d145bb405e8a4586002b877680"
PAYLOAD_TREE_SHA256 = "8544e551832c929eecad0cf9898204fd673bd4a37a0a6f37433865afbb3556cb"
PAYLOAD_FILE_COUNT = 9_241
PAYLOAD_WEM_COUNT = 8_969
PAYLOAD_BNK_COUNT = 272
PAYLOAD_UNCOMPRESSED_SIZE = 605_706_607
PAYLOAD_MAX_FILE_SIZE = 74_956_066

COPY_CHUNK_SIZE = 1024 * 1024
ARCHIVE_MTIME = 1_577_836_800  # 2020-01-01T00:00:00Z


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(COPY_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def require_regular_file(path: Path, *, exclusive: bool = False) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise SystemExit(f"Arquivo obrigatorio ausente ou ilegivel: {path}: {exc}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(reparse_flag and file_attributes & reparse_flag)
        or (exclusive and metadata.st_nlink != 1)
    ):
        raise SystemExit(f"Arquivo obrigatorio nao e regular e exclusivo: {path}")
    return metadata


def _assert_unchanged(path: Path, before: os.stat_result, label: str) -> None:
    try:
        after = path.lstat()
    except OSError as exc:
        raise SystemExit(f"{label} mudou durante o empacotamento.") from exc
    if (
        not stat.S_ISREG(after.st_mode)
        or after.st_nlink != 1
        or (after.st_dev, after.st_ino, after.st_size)
        != (before.st_dev, before.st_ino, before.st_size)
    ):
        raise SystemExit(f"{label} mudou durante o empacotamento.")


def _safe_relative(name: str, *, label: str) -> str:
    if not name or "\\" in name or ":" in name or "\x00" in name:
        raise SystemExit(f"Caminho inseguro em {label}: {name!r}")
    parts = name.split("/")
    path = PurePosixPath(*parts)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in parts)
        or path.as_posix() != name
        or unicodedata.normalize("NFC", name) != name
        or any(part.endswith((" ", ".")) for part in parts)
    ):
        raise SystemExit(f"Caminho inseguro em {label}: {name!r}")
    return name


def _safe_payload_relative(name: str) -> str:
    prefix = "patch_data/"
    if not name.startswith(prefix):
        raise SystemExit(f"Layout inesperado no payload: {name!r}")
    relative = _safe_relative(name[len(prefix) :], label="payload")
    if PurePosixPath(relative).suffix.casefold() not in {".wem", ".bnk"}:
        raise SystemExit(f"Extensao inesperada no payload: {name!r}")
    return relative


def _canonical_key(name: str) -> tuple[str, str]:
    return (unicodedata.normalize("NFC", name).casefold(), name)


def _resolve_runtime_link(member_name: str, link_name: str) -> str:
    """Resolve a tar symlink lexically and require it to remain below python/."""

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
        raise SystemExit("Runtime portatil nao e um tar.gz integro.") from exc

    if not infos or len(infos) > RUNTIME_MAX_MEMBERS:
        raise SystemExit("Quantidade insegura de membros no runtime portatil.")
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
        # Linux paths are case-sensitive.  The authenticated Astral runtime
        # legitimately contains terminfo names that differ only by case.
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


def validate_runtime(path: Path) -> os.stat_result:
    if path.name != RUNTIME_ARCHIVE_NAME:
        raise SystemExit(f"Nome obrigatorio do runtime: {RUNTIME_ARCHIVE_NAME}")
    before = require_regular_file(path, exclusive=True)
    if before.st_size != RUNTIME_ARCHIVE_SIZE:
        raise SystemExit(
            "Tamanho incorreto do runtime: "
            f"esperado {RUNTIME_ARCHIVE_SIZE}, obtido {before.st_size}"
        )
    actual = sha256(path)
    if actual != RUNTIME_SHA256:
        raise SystemExit(
            f"SHA-256 incorreto do runtime: esperado {RUNTIME_SHA256}, obtido {actual}"
        )
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (
            opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino, opened.st_size)
            != (before.st_dev, before.st_ino, before.st_size)
        ):
            raise SystemExit("O runtime mudou durante a validacao.")
        _validate_runtime_tar(stream)
    _assert_unchanged(path, before, "O runtime")
    return before


def validate_payload(path: Path) -> os.stat_result:
    before = require_regular_file(path, exclusive=True)
    if before.st_size != PAYLOAD_ARCHIVE_SIZE:
        raise SystemExit(
            "Tamanho incorreto do payload: "
            f"esperado {PAYLOAD_ARCHIVE_SIZE}, obtido {before.st_size}"
        )
    actual = sha256(path)
    if actual != PAYLOAD_SHA256:
        raise SystemExit(
            f"SHA-256 incorreto do payload: esperado {PAYLOAD_SHA256}, obtido {actual}"
        )
    _assert_unchanged(path, before, "O payload")
    return before


def _validated_payload_entries(
    infos: list[zipfile.ZipInfo],
) -> list[tuple[str, zipfile.ZipInfo]]:
    if len(infos) != PAYLOAD_FILE_COUNT:
        raise SystemExit(
            "Quantidade de arquivos divergente no payload: "
            f"esperado {PAYLOAD_FILE_COUNT}, obtido {len(infos)}"
        )
    entries: list[tuple[str, zipfile.ZipInfo]] = []
    seen: set[str] = set()
    wem_count = bnk_count = total_size = max_file_size = 0
    for info in infos:
        relative = _safe_payload_relative(info.filename)
        folded = unicodedata.normalize("NFC", relative).casefold()
        if folded in seen:
            raise SystemExit(f"Nome duplicado no payload: {relative!r}")
        seen.add(folded)
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if (
            info.is_dir()
            or stat.S_IFMT(unix_mode) not in (0, stat.S_IFREG)
            or info.flag_bits & 0x1
            or info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
            or info.file_size < 0
            or info.file_size > PAYLOAD_MAX_FILE_SIZE
            or info.compress_size < 0
            or info.compress_size > PAYLOAD_ARCHIVE_SIZE
        ):
            raise SystemExit(f"Membro inseguro no payload: {info.filename!r}")
        total_size += info.file_size
        if total_size > PAYLOAD_UNCOMPRESSED_SIZE:
            raise SystemExit("O payload excede o tamanho autenticado.")
        max_file_size = max(max_file_size, info.file_size)
        if relative.casefold().endswith(".wem"):
            wem_count += 1
        else:
            bnk_count += 1
        entries.append((relative, info))
    if entries != sorted(entries, key=lambda item: _canonical_key(item[0])):
        raise SystemExit("As entradas do payload estao fora da ordem canonica.")
    if (
        wem_count != PAYLOAD_WEM_COUNT
        or bnk_count != PAYLOAD_BNK_COUNT
        or total_size != PAYLOAD_UNCOMPRESSED_SIZE
        or max_file_size != PAYLOAD_MAX_FILE_SIZE
    ):
        raise SystemExit(
            "Estatisticas divergentes no payload: "
            f"WEM={wem_count}, BNK={bnk_count}, bytes={total_size}, maior={max_file_size}"
        )
    return entries


def release_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    suffix = path.suffix.casefold()
    if suffix not in TEXT_SUFFIXES and path.name.casefold() != "license":
        return data
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SystemExit(f"Arquivo de texto nao UTF-8: {path}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _tar_info(name: str, *, size: int = 0, directory: bool = False, mode: int = 0o644) -> tarfile.TarInfo:
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE if directory else tarfile.REGTYPE
    info.size = 0 if directory else size
    info.mode = 0o755 if directory else mode
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = ARCHIVE_MTIME
    return info


class _AuditedReader:
    def __init__(self, raw: BinaryIO, digest: Any, *, header_size: int = 0):
        self.raw = raw
        self.digest = digest
        self.header_size = header_size
        self.header = bytearray()
        self.count = 0

    def read(self, size: int = -1) -> bytes:
        data = self.raw.read(size)
        if data:
            self.digest.update(data)
            self.count += len(data)
            if len(self.header) < self.header_size:
                self.header.extend(data[: self.header_size - len(self.header)])
        return data


def _add_file(archive: tarfile.TarFile, name: str, data: bytes, mode: int) -> None:
    archive.addfile(_tar_info(name, size=len(data), mode=mode), io.BytesIO(data))


def _validate_versions(root: Path, version: str) -> None:
    plain = version.removeprefix("v")
    try:
        init_source = (root / "patcher/__init__.py").read_text(encoding="utf-8")
        gui_source = (root / "patcher/patcher_gui.py").read_text(encoding="utf-8")
        linux_source = (root / "interno/INICIAR_LINUX.sh").read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Nao foi possivel ler as versoes do pacote: {exc}") from exc
    init_match = re.search(r'^__version__\s*=\s*"([^"]+)"', init_source, re.MULTILINE)
    gui_match = re.search(r'^PATCHER_VERSION\s*=\s*"([^"]+)"', gui_source, re.MULTILINE)
    linux_match = re.search(r'^readonly APP_VERSION="([^"]+)"', linux_source, re.MULTILINE)
    if (
        not init_match
        or not gui_match
        or not linux_match
        or {init_match.group(1), gui_match.group(1), linux_match.group(1)} != {plain}
    ):
        raise SystemExit(
            "A tag, patcher.__version__, PATCHER_VERSION e APP_VERSION precisam coincidir."
        )
    runtime_controls = (
        f'readonly RUNTIME_NAME="{RUNTIME_ARCHIVE_NAME}"',
        f'readonly RUNTIME_SIZE="{RUNTIME_ARCHIVE_SIZE}"',
        f'readonly RUNTIME_SHA256="{RUNTIME_SHA256}"',
    )
    missing = [item for item in runtime_controls if item not in linux_source]
    if missing:
        raise SystemExit(f"Constantes do runtime divergentes no launcher: {missing}")


def _publish_without_replace(temporary: Path, output: Path) -> None:
    if os.path.lexists(output):
        raise SystemExit(f"O artefato de saida ja existe e foi preservado: {output}")
    if os.name == "nt":
        os.rename(temporary, output)
    else:
        try:
            os.link(temporary, output)
        except FileExistsError as exc:
            raise SystemExit(
                f"O artefato de saida apareceu durante o build e foi preservado: {output}"
            ) from exc
        temporary.unlink()


def build(
    root: Path,
    wheelhouse: Path,
    payload: Path,
    runtime: Path,
    output: Path,
    version: str,
) -> None:
    if not re.fullmatch(r"v\d+\.\d+\.\d+", version):
        raise SystemExit(f"Versao invalida: {version!r}")
    if version != FINAL_VERSION:
        raise SystemExit(f"Este empacotador esta fixado em {FINAL_VERSION}, nao {version}.")
    if output.name != FINAL_ARCHIVE_NAME:
        raise SystemExit(f"Nome obrigatorio do release Linux: {FINAL_ARCHIVE_NAME}")
    if FINAL_PACKAGE_ROOT != f"ERPT-BR-{version}-Linux-x86_64":
        raise SystemExit("A raiz fixa do pacote diverge da versao final.")
    _validate_versions(root, version)

    source_members: dict[str, bytes] = {}
    for relative in SOURCE_FILES:
        source = root / relative
        require_regular_file(source)
        source_members[relative] = release_bytes(source)

    actual_wheels = {item.name for item in wheelhouse.glob("*.whl") if item.is_file()}
    if actual_wheels != set(WHEELS):
        missing = sorted(set(WHEELS) - actual_wheels)
        extra = sorted(actual_wheels - set(WHEELS))
        raise SystemExit(f"Wheelhouse Linux divergente; ausentes={missing}, extras={extra}")
    wheel_stats: dict[str, os.stat_result] = {}
    for name, (expected_size, expected_hash) in WHEELS.items():
        wheel = wheelhouse / name
        metadata = require_regular_file(wheel, exclusive=True)
        if metadata.st_size != expected_size or sha256(wheel) != expected_hash:
            raise SystemExit(f"Tamanho ou SHA-256 incorreto para {name}")
        wheel_stats[name] = metadata

    runtime_stat = validate_runtime(runtime)
    payload_stat = validate_payload(payload)

    try:
        payload_stream = payload.open("rb")
    except OSError as exc:
        raise SystemExit(f"Payload ausente ou ilegivel: {payload}") from exc
    temporary: Path | None = None
    temporary_identity: tuple[int, int] | None = None
    try:
        opened_payload = os.fstat(payload_stream.fileno())
        if (
            opened_payload.st_nlink != 1
            or (opened_payload.st_dev, opened_payload.st_ino, opened_payload.st_size)
            != (payload_stat.st_dev, payload_stat.st_ino, payload_stat.st_size)
        ):
            raise SystemExit("O payload mudou antes do empacotamento.")
        try:
            payload_zip = zipfile.ZipFile(payload_stream, "r")
            if payload_zip.comment:
                raise SystemExit("O payload contem comentario inesperado.")
            payload_entries = _validated_payload_entries(payload_zip.infolist())
        except SystemExit:
            raise
        except (OSError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
            raise SystemExit("Falha de integridade ou CRC no payload de entrada.") from exc

        file_names = set(SOURCE_FILES)
        file_names.update(f"wheelhouse/{name}" for name in WHEELS)
        file_names.add(f"runtime/{RUNTIME_ARCHIVE_NAME}")
        file_names.update(f"patch_data/{relative}" for relative, _ in payload_entries)
        directories = {FINAL_PACKAGE_ROOT}
        for relative in file_names:
            parts = PurePosixPath(relative).parts
            for index in range(1, len(parts)):
                directories.add(
                    f"{FINAL_PACKAGE_ROOT}/{PurePosixPath(*parts[:index]).as_posix()}"
                )

        output.parent.mkdir(parents=True, exist_ok=True)
        if os.path.lexists(output):
            raise SystemExit(f"O artefato de saida ja existe e foi preservado: {output}")
        temporary = output.with_name(f".{output.name}.{uuid.uuid4().hex}.tmp")
        raw_output = temporary.open("xb")
        temporary_metadata = temporary.lstat()
        temporary_identity = (temporary_metadata.st_dev, temporary_metadata.st_ino)
        try:
            with raw_output:
                with gzip.GzipFile(
                    filename="", mode="wb", fileobj=raw_output, compresslevel=9, mtime=0
                ) as gzip_stream:
                    with tarfile.open(
                        fileobj=gzip_stream, mode="w|", format=tarfile.USTAR_FORMAT
                    ) as archive:
                        for directory in sorted(directories, key=_canonical_key):
                            archive.addfile(_tar_info(directory, directory=True))

                        payload_by_name = {
                            f"patch_data/{relative}": info
                            for relative, info in payload_entries
                        }
                        payload_tree = hashlib.sha256()
                        for relative in sorted(file_names, key=_canonical_key):
                            target = f"{FINAL_PACKAGE_ROOT}/{relative}"
                            if relative in source_members:
                                mode = 0o755 if relative in EXECUTABLE_FILES else 0o644
                                _add_file(archive, target, source_members[relative], mode)
                                continue
                            if relative.startswith("wheelhouse/"):
                                wheel_name = relative.removeprefix("wheelhouse/")
                                wheel_path = wheelhouse / wheel_name
                                with wheel_path.open("rb") as stream:
                                    archive.addfile(
                                        _tar_info(
                                            target,
                                            size=WHEELS[wheel_name][0],
                                            mode=0o644,
                                        ),
                                        stream,
                                    )
                                _assert_unchanged(
                                    wheel_path, wheel_stats[wheel_name], f"A wheel {wheel_name}"
                                )
                                continue
                            if relative.startswith("runtime/"):
                                with runtime.open("rb") as stream:
                                    archive.addfile(
                                        _tar_info(
                                            target, size=RUNTIME_ARCHIVE_SIZE, mode=0o644
                                        ),
                                        stream,
                                    )
                                _assert_unchanged(runtime, runtime_stat, "O runtime")
                                continue

                            info = payload_by_name[relative]
                            payload_relative = relative.removeprefix("patch_data/")
                            encoded = payload_relative.encode("utf-8")
                            payload_tree.update(struct.pack("<I", len(encoded)))
                            payload_tree.update(encoded)
                            payload_tree.update(struct.pack("<Q", info.file_size))
                            try:
                                with payload_zip.open(info, "r") as member:
                                    audited = _AuditedReader(
                                        member, payload_tree, header_size=12
                                    )
                                    archive.addfile(
                                        _tar_info(target, size=info.file_size, mode=0o644),
                                        audited,
                                    )
                            except (OSError, EOFError, RuntimeError, zipfile.BadZipFile) as exc:
                                raise SystemExit(
                                    f"Falha ao ler o payload: {payload_relative!r}"
                                ) from exc
                            if audited.count != info.file_size:
                                raise SystemExit(
                                    f"Leitura incompleta no payload: {payload_relative!r}"
                                )
                            if payload_relative.casefold().endswith(".wem"):
                                valid_header = (
                                    len(audited.header) >= 12
                                    and audited.header[:4] == b"RIFF"
                                    and audited.header[8:12] == b"WAVE"
                                )
                            else:
                                valid_header = (
                                    len(audited.header) >= 4
                                    and audited.header[:4] == b"BKHD"
                                )
                            if not valid_header:
                                raise SystemExit(
                                    f"Cabecalho de audio invalido: {payload_relative!r}"
                                )
                        if payload_tree.hexdigest() != PAYLOAD_TREE_SHA256:
                            raise SystemExit("SHA-256 da arvore do payload divergiu.")
        finally:
            if not raw_output.closed:
                raw_output.close()

        _assert_unchanged(payload, payload_stat, "O payload")
        _publish_without_replace(temporary, output)
        temporary = None
    finally:
        payload_stream.close()
        try:
            payload_zip.close()  # type: ignore[possibly-undefined]
        except (NameError, OSError):
            pass
        if temporary is not None:
            try:
                metadata = temporary.lstat()
                if (
                    temporary_identity is not None
                    and stat.S_ISREG(metadata.st_mode)
                    and metadata.st_nlink == 1
                    and (metadata.st_dev, metadata.st_ino) == temporary_identity
                ):
                    temporary.unlink()
            except (FileNotFoundError, IsADirectoryError, PermissionError, OSError):
                pass


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--payload", type=Path, required=True)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    build(
        args.root.resolve(),
        args.wheelhouse.resolve(),
        args.payload.absolute(),
        args.runtime.absolute(),
        args.output.absolute(),
        args.version,
    )
    print(f"Criado: {args.output} ({sha256(args.output)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
