"""Core sicuro del patcher ERITA.

Questo modulo non avvia il gioco, non inietta DLL e non modifica l'Easy Anti-Cheat.
Sostituisce solamente gli slot audio esistenti nei file ``sd*.bdt`` dopo
aver validato tutti i dati e creato un backup transazionale della build attuale.
"""

from __future__ import annotations

import bisect
import copy
import ctypes
import errno
import hashlib
import json
import os
import re
import shutil
import stat
import struct
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import AbstractSet, BinaryIO, Callable, Iterable, Mapping, Sequence

try:
    from .bnk import BnkMergeError, merge_bnk_with_vanilla
except ImportError:  # pragma: no cover - suporte a execucao direta da interface
    from bnk import BnkMergeError, merge_bnk_with_vanilla


ELDEN_RING_SD_KEY_PEM = """-----BEGIN RSA PUBLIC KEY-----
MIIBCwKCAQEAmYJ/5GJU4boJSvZ81BFOHYTGdBWPHnWYly3yWo01BYjGRnz8NTkz
DHUxsbjIgtG5XqsQfZstZILQ97hgSI5AaAoCGrT8sn0PeXg2i0mKwL21gRjRUdvP
Dp1Y+7hgrGwuTkjycqqsQ/qILm4NvJHvGRd7xLOJ9rs2zwYhceRVrq9XU2AXbdY4
pdCQ3+HuoaFiJ0dW0ly5qdEXjbSv2QEYe36nWCtsd6hEY9LjbBX8D1fK3D2c6C0g
NdHJGH2iEONUN6DMK9t0v2JBnwCOZQ7W+Gt7SpNNrkx8xKEM8gH9na10g9ne11Mi
O1FnLm8i4zOxVdPHQBKICkKcGS1o3C2dfwIEXw/f3w==
-----END RSA PUBLIC KEY-----"""

ARCHIVE_NAME_RE = re.compile(r"^sd(?:_dlc\d+)?\.bhd$", re.IGNORECASE)
BDT_NAME_RE = re.compile(r"^sd(?:_dlc\d+)?\.bdt$", re.IGNORECASE)
MIN_MATCH_RATIO = 1.0
BACKUP_SCHEMA = 1
COPY_BUFFER_SIZE = 8 * 1024 * 1024
MAX_BHD_FILE_SIZE = 64 * 1024 * 1024
BHD_INTEGRITY_STRICT = "strict"
BHD_INTEGRITY_SCOPED_MOD = "scoped_mod"
BHD_INTEGRITY_MODES = frozenset(
    {BHD_INTEGRITY_STRICT, BHD_INTEGRITY_SCOPED_MOD}
)
TRANSACTION_FILE_RE = re.compile(
    r"^\.erita-[0-9a-f]{32}-sd(?:_dlc\d+)?\.bdt\.(?:rollback|displaced)$",
    re.IGNORECASE,
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PatcherError(RuntimeError):
    """Errore atteso, presentabile all'utente."""


class CompatibilityError(PatcherError):
    """Il file del gioco o il payload non è compatibile."""


class LegacyBackupError(PatcherError):
    """È stato trovato un backup non sicuro di una versione precedente."""


class BackupError(PatcherError):
    """Errore nella creazione, validazione o ripristino del backup."""


class ArchiveProfileError(CompatibilityError, BackupError):
    """I file reali non soddisfano un profilo audio omologato."""

    code = "ERITA-FILES-001"


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _read_regular_file_limited(
    path: Path,
    *,
    max_size: int,
    label: str,
) -> bytes:
    """Read a small authority file without following swaps, links or hardlinks."""

    try:
        before = path.lstat()
    except OSError as exc:
        raise CompatibilityError(f"Impossibile ispezionare {label}: {exc}") from exc
    if (
        _metadata_is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size <= 0
        or before.st_size > max_size
    ):
        raise CompatibilityError(
            f"{label} non è un file regolare esclusivo entro il limite di "
            f"{max_size} byte."
        )
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise CompatibilityError(f"Impossibile aprire {label}: {exc}") from exc
    try:
        opened = os.fstat(stream.fileno())
        current = path.lstat()
        if (
            _metadata_is_link_or_reparse(current)
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or opened.st_nlink != 1
            or current.st_nlink != 1
            or opened.st_size != before.st_size
            or current.st_size != before.st_size
            or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
            or (current.st_dev, current.st_ino) != (before.st_dev, before.st_ino)
        ):
            raise CompatibilityError(f"{label} è cambiato durante l'apertura.")
        data = stream.read(max_size + 1)
        opened_after = os.fstat(stream.fileno())
        current_after = path.lstat()
        if (
            len(data) != before.st_size
            or len(data) > max_size
            or _metadata_is_link_or_reparse(current_after)
            or opened_after.st_size != before.st_size
            or current_after.st_size != before.st_size
            or opened_after.st_mtime_ns != opened.st_mtime_ns
            or (opened_after.st_dev, opened_after.st_ino)
            != (before.st_dev, before.st_ino)
            or (current_after.st_dev, current_after.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise CompatibilityError(f"{label} è cambiato durante la lettura.")
        return data
    except OSError as exc:
        raise CompatibilityError(f"Lettura di {label} non riuscita: {exc}") from exc
    finally:
        stream.close()


def _absolute_without_resolving(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _is_windows() -> bool:
    return os.name == "nt"


def _path_identity_text(path: str | os.PathLike[str]) -> str:
    """Return a stable path key without merging case-distinct POSIX paths."""

    value = os.fspath(path)
    return value.casefold() if _is_windows() else value


def _linux_rename_noreplace(source: Path, destination: Path) -> None:
    """Call Linux ``renameat2(RENAME_NOREPLACE)`` or fail before mutation."""

    try:
        libc = ctypes.CDLL(None, use_errno=True)
        renameat2 = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise OSError(
            errno.ENOTSUP,
            "renameat2(RENAME_NOREPLACE) non è disponibile su questo Linux",
            str(destination),
        ) from exc
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = renameat2(
        -100,  # AT_FDCWD
        os.fsencode(source),
        -100,  # AT_FDCWD
        os.fsencode(destination),
        1,  # RENAME_NOREPLACE
    )
    if result != 0:
        error_number = ctypes.get_errno() or errno.EIO
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(destination),
        )


def _fsync_directory(path: Path) -> None:
    """Persist directory metadata on POSIX; Windows has different semantics."""

    if _is_windows():
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_CLOEXEC", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Atomically rename without replacing a racing destination."""

    source = _absolute_without_resolving(source)
    destination = _absolute_without_resolving(destination)
    if _is_windows():
        os.rename(source, destination)
    elif sys.platform.startswith("linux"):
        _linux_rename_noreplace(source, destination)
    else:
        raise OSError(
            errno.ENOTSUP,
            f"rename atomico senza sostituzione non supportato su {sys.platform}",
            str(destination),
        )
    for parent in dict.fromkeys((source.parent, destination.parent)):
        _fsync_directory(parent)


def _ensure_safe_directory_tree(
    path: str | os.PathLike[str], *, label: str, create: bool = True
) -> Path:
    """Validate lexical ancestors and never follow a link/reparse for backups."""

    target = _absolute_without_resolving(path)
    for current in (*reversed(target.parents), target):
        if os.path.lexists(current):
            try:
                metadata = current.lstat()
            except OSError as exc:
                raise BackupError(
                    f"Impossibile ispezionare {label} '{current}': {exc}"
                ) from exc
            if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
                metadata.st_mode
            ):
                raise BackupError(
                    f"{label} contiene link, reparse point o tipo non sicuro: '{current}'."
                )
            continue
        if not create:
            return target
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise BackupError(
                f"Impossibile creare {label} '{current}': {exc}"
            ) from exc
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise BackupError(
                f"Impossibile confermare {label} '{current}': {exc}"
            ) from exc
        if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise BackupError(
                f"{label} è riapparso come link, reparse point o tipo non sicuro: '{current}'."
            )
    return target


def _open_safe_operation_lock(path: Path):
    """Open a lock without writing through a pre-existing link or hardlink."""

    _ensure_safe_directory_tree(path.parent, label="La cartella del lock di backup")
    before: os.stat_result | None = None
    try:
        stream = path.open("x+b")
    except FileExistsError:
        try:
            before = path.lstat()
        except OSError as exc:
            raise BackupError(f"Lock di backup non sicuro: '{path}': {exc}") from exc
        if (
            _metadata_is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
        ):
            raise BackupError(
                f"Il lock di backup non è un file regolare esclusivo: '{path}'."
            )
        try:
            stream = path.open("r+b")
        except OSError as exc:
            raise BackupError(f"Lock di backup non sicuro: '{path}': {exc}") from exc
    except OSError as exc:
        raise BackupError(f"Impossibile creare il lock di backup: {exc}") from exc

    try:
        opened = os.fstat(stream.fileno())
        current = path.lstat()
        if (
            _metadata_is_link_or_reparse(current)
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or opened.st_nlink != 1
            or current.st_nlink != 1
            or opened.st_size != current.st_size
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            or (
                before is not None
                and (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
            )
        ):
            raise BackupError(f"Il lock di backup è cambiato o possiede un hardlink: '{path}'.")

        # Recover only the exact zero-byte inode left if the prior process died
        # after exclusive creation and before initialization.
        if opened.st_size == 0:
            stream.write(b"\0")
            stream.flush()
            os.fsync(stream.fileno())
        opened = os.fstat(stream.fileno())
        current = path.lstat()
        if (
            _metadata_is_link_or_reparse(current)
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or opened.st_nlink != 1
            or current.st_nlink != 1
            or opened.st_size < 1
            or opened.st_size != current.st_size
            or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
            or (
                before is not None
                and (before.st_dev, before.st_ino) != (current.st_dev, current.st_ino)
            )
        ):
            raise BackupError(f"Il lock di backup è cambiato o possiede un hardlink: '{path}'.")
        stream.seek(0)
        return stream
    except Exception:
        stream.close()
        raise


@dataclass(frozen=True)
class AESRange:
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class AESKeyInfo:
    key: bytes
    ranges: tuple[AESRange, ...] = ()


@dataclass(frozen=True)
class SHAHashInfo:
    hash_bytes: bytes
    ranges: tuple[AESRange, ...] = ()


@dataclass(frozen=True)
class FileEntry:
    file_name_hash: int
    padded_file_size: int
    unpadded_file_size: int
    file_offset: int
    sha_hash_offset: int
    aes_key_offset: int
    sha_info: SHAHashInfo | None = None
    aes_info: AESKeyInfo | None = None


@dataclass(frozen=True)
class Archive:
    bhd_path: Path
    bdt_path: Path
    bhd_sha256: str
    bdt_size: int
    bdt_mtime_ns: int
    entries: tuple[FileEntry, ...]
    salt: bytes = b""
    rsa_encrypted_bhd: bool = False


@dataclass(frozen=True)
class ArchiveFingerprint:
    """Identità immutabile di una coppia BHD/BDT vanilla omologata."""

    stem: str
    bhd_sha256: str
    bdt_size: int
    original_bdt_sha256: str

    def __post_init__(self) -> None:
        if (
            not re.fullmatch(r"sd(?:_dlc\d+)?", self.stem, re.IGNORECASE)
            or not SHA256_RE.fullmatch(self.bhd_sha256)
            or not isinstance(self.bdt_size, int)
            or self.bdt_size <= 0
            or not SHA256_RE.fullmatch(self.original_bdt_sha256)
        ):
            raise ValueError(f"Fingerprint di archivio non valido: {self.stem!r}.")


@dataclass(frozen=True)
class GameArchiveProfile:
    """Profilo crittografico degli archivi che autorizzano un payload."""

    profile_id: str
    archives: tuple[ArchiveFingerprint, ...]

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", self.profile_id):
            raise ValueError(f"Identificatore di profilo non valido: {self.profile_id!r}.")
        stems = [item.stem.casefold() for item in self.archives]
        if not stems or len(stems) != len(set(stems)):
            raise ValueError("Il profilo degli archivi è vuoto o contiene duplicati.")


@dataclass(frozen=True)
class EntryTarget:
    archive: Archive
    entry: FileEntry


@dataclass(frozen=True)
class Replacement:
    source_path: Path
    source_relative: str
    game_path: str
    file_hash: int
    targets: tuple[EntryTarget, ...]


@dataclass(frozen=True)
class PreparedWrite:
    replacement: Replacement
    target: EntryTarget
    source_sha256: str


@dataclass(frozen=True)
class PatchPlan:
    writes: tuple[PreparedWrite, ...]
    payload_file_count: int
    matched_file_count: int
    unmatched_files: tuple[str, ...]
    payload_file_sha256: tuple[tuple[str, str], ...]

    @property
    def match_ratio(self) -> float:
        if self.payload_file_count == 0:
            return 0.0
        return self.matched_file_count / self.payload_file_count

    @property
    def touched_archives(self) -> tuple[Archive, ...]:
        by_path: dict[Path, Archive] = {}
        for write in self.writes:
            by_path[write.target.archive.bdt_path] = write.target.archive
        return tuple(by_path[path] for path in sorted(by_path, key=str))


def _planned_external_wem_ids(plan: PatchPlan) -> frozenset[int]:
    """Return only numeric WEM ids that have an actual write in ``plan``.

    A BNK may redirect a prefetched sound to an external WEM only when that
    exact WEM is part of the authenticated plan.  Merely finding a numeric
    filename in the payload tree is insufficient because it may be unmatched
    on the target build.
    """

    result: set[int] = set()
    for write in plan.writes:
        source = write.replacement.source_path
        if source.suffix.lower() != ".wem" or not source.stem.isdecimal():
            continue
        wem_id = int(source.stem, 10)
        if wem_id <= 0xFFFFFFFF:
            result.add(wem_id)
    return frozenset(result)


@dataclass(frozen=True)
class BHDEntryIdentity:
    """Stable identity for one authenticated BHD entry within a loaded build."""

    archive_path: Path
    entry_index: int
    file_name_hash: int
    file_offset: int
    padded_file_size: int


@dataclass(frozen=True)
class BHDIntegrityAssessment:
    """Result of comparing a pristine BDT baseline with the planned slot bytes."""

    validated_entry_count: int
    divergent_entries: frozenset[BHDEntryIdentity]
    validated_archive_sha256: tuple[tuple[Path, str], ...] = ()
    validated_archive_identities: tuple[tuple[Path, tuple[int, int]], ...] = ()


def _require_slice(data: bytes, offset: int, size: int, label: str) -> None:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise CompatibilityError(
            f"BHD non valido: {label} fuori dai limiti "
            f"(offset={offset}, dimensione={size}, file={len(data)})."
        )


def _read_i32(data: bytes, offset: int, label: str) -> int:
    _require_slice(data, offset, 4, label)
    return struct.unpack_from("<i", data, offset)[0]


def _read_i64(data: bytes, offset: int, label: str) -> int:
    _require_slice(data, offset, 8, label)
    return struct.unpack_from("<q", data, offset)[0]


def _read_u64(data: bytes, offset: int, label: str) -> int:
    _require_slice(data, offset, 8, label)
    return struct.unpack_from("<Q", data, offset)[0]


def _read_ranges(
    data: bytes,
    offset: int,
    slot_size: int,
    label: str,
    block_size: int | None = None,
) -> tuple[AESRange, ...]:
    count = _read_i32(data, offset, f"{label}.count")
    if count < 0 or count > 1_000_000:
        raise CompatibilityError(
            f"BHD non valido: quantità di range in {label}: {count}."
        )
    _require_slice(data, offset + 4, count * 16, label)
    ranges: list[AESRange] = []
    pos = offset + 4
    for index in range(count):
        start = _read_i64(data, pos, f"{label}[{index}].start")
        end = _read_i64(data, pos + 8, f"{label}[{index}].end")
        pos += 16
        # SoulsFormats treats either -1 endpoint as an unused sentinel range.
        if start == -1 or end == -1:
            ranges.append(AESRange(start, end))
            continue
        if start < 0 or end < start or end > slot_size:
            raise CompatibilityError(
                f"BHD non valido: range {label}[{index}] fuori dallo slot "
                f"({start}..{end}, slot={slot_size})."
            )
        if block_size is not None and (end - start) % block_size:
            raise CompatibilityError(
                f"BHD non valido: il range {label}[{index}] ha dimensione "
                f"{end - start}, che non è multiplo di {block_size}."
            )
        ranges.append(AESRange(start, end))
    return tuple(ranges)


def rsa_decrypt_bhd(encrypted: bytes, pem_key: str = ELDEN_RING_SD_KEY_PEM) -> bytes:
    """Decifra un BHD come il RsaEngine usato dagli strumenti Souls."""
    try:
        from Crypto.PublicKey import RSA
    except ImportError as exc:  # pragma: no cover - dipende dall'installazione locale
        raise PatcherError(
            "Dipendenza PyCryptodome mancante. Esegui di nuovo ERITA.cmd."
        ) from exc

    key = RSA.import_key(pem_key)
    input_size = (key.size_in_bits() + 7) // 8
    output_size = input_size - 1
    if not encrypted or len(encrypted) % input_size:
        raise CompatibilityError(
            "Indice BHD RSA con un numero incompleto di blocchi."
        )
    result = bytearray()
    for pos in range(0, len(encrypted), input_size):
        block = encrypted[pos : pos + input_size]
        ciphertext = int.from_bytes(block, "big")
        if ciphertext <= 0 or ciphertext >= key.n:
            raise CompatibilityError(
                f"L'indice BHD RSA ha un blocco non canonico alla posizione {pos}."
            )
        value = pow(ciphertext, key.e, key.n)
        if value.bit_length() > output_size * 8:
            raise CompatibilityError(
                f"L'indice BHD RSA ha un blocco decifrato non valido alla posizione {pos}."
            )
        try:
            result.extend(value.to_bytes(output_size, "big"))
        except OverflowError as exc:  # defesa adicional para backends alternativos
            raise CompatibilityError(
                f"L'indice BHD RSA supera il blocco atteso alla posizione {pos}."
            ) from exc
    return bytes(result)


def _validated_bhd5_data_and_salt(data: bytes) -> tuple[bytes, bytes]:
    _require_slice(data, 0, 32, "intestazione")
    if data[:4] != b"BHD5":
        raise CompatibilityError(f"Formato BHD sconosciuto: {data[:4]!r}.")
    # Elden Ring PC uses the little-endian BHD5 variant (0xFF == signed -1).
    # Supporting the generic big-endian variant would require changing every
    # integer read below, so reject it explicitly rather than misparse offsets.
    if data[4] != 0xFF:
        raise CompatibilityError(
            f"BHD5 con endianness non supportata per Elden Ring PC: 0x{data[4]:02x}."
        )
    if data[6:8] != b"\0\0" or _read_i32(data, 8, "version") != 1:
        raise CompatibilityError("BHD5 con intestazione/versione inaspettata.")
    declared_size = _read_i32(data, 12, "file_size")
    salt_length = _read_i32(data, 24, "salt_length")
    if declared_size < 28 or declared_size > len(data):
        raise CompatibilityError(
            f"BHD5 con dimensione logica non valida ({declared_size}, buffer={len(data)})."
        )
    padding = data[declared_size:]
    if len(padding) >= 255 or any(padding):
        raise CompatibilityError(
            "BHD5 con padding RSA non canonico dopo la dimensione logica."
        )
    if salt_length < 0 or 28 + salt_length > declared_size:
        raise CompatibilityError(f"BHD5 con salt_length non valido: {salt_length}.")
    # RSA block decoding may append zero padding after the logical BHD size.
    # All subsequent offsets are constrained to the declared logical file.
    logical_data = data[:declared_size]
    return logical_data, logical_data[28 : 28 + salt_length]


def parse_bhd5_salt(data: bytes) -> bytes:
    """Return the exact salt used by BHD5 per-entry SHA-256 metadata."""

    _logical_data, salt = _validated_bhd5_data_and_salt(data)
    return salt


def calculate_bhd5_salted_sha256(
    slot_data: bytes,
    salt: bytes,
    ranges: Sequence[AESRange],
) -> bytes:
    """Hash BHD5 ranges in declaration order, followed by the archive salt."""

    digest = hashlib.sha256()
    for index, item in enumerate(ranges):
        if item.start_offset == -1 or item.end_offset == -1:
            continue
        if (
            item.start_offset < 0
            or item.end_offset < item.start_offset
            or item.end_offset > len(slot_data)
        ):
            raise CompatibilityError(
                f"Range SHA[{index}] fora do slot de destino "
                f"({item.start_offset}..{item.end_offset}, slot={len(slot_data)})."
            )
        digest.update(slot_data[item.start_offset : item.end_offset])
    digest.update(salt)
    return digest.digest()


def _validated_bhd_integrity_mode(mode: str) -> str:
    if mode not in BHD_INTEGRITY_MODES:
        supported = ", ".join(sorted(BHD_INTEGRITY_MODES))
        raise ValueError(
            f"Modalità di integrità BHD sconosciuta: {mode!r}. "
            f"Modalità supportate: {supported}."
        )
    return mode


def _bhd_entry_identity(
    archive: Archive,
    entry_index: int,
    entry: FileEntry,
) -> BHDEntryIdentity:
    return BHDEntryIdentity(
        archive_path=archive.bdt_path,
        entry_index=entry_index,
        file_name_hash=entry.file_name_hash,
        file_offset=entry.file_offset,
        padded_file_size=entry.padded_file_size,
    )


def validate_patch_plan_sha_integrity(
    plan: PatchPlan,
    *,
    archives: Sequence[Archive] | None = None,
    mode: str = BHD_INTEGRITY_STRICT,
    baseline_paths: Mapping[Path, Path] | None = None,
    merge_bnk_from_baseline: bool = False,
    require_entry_sha_metadata: bool = False,
) -> BHDIntegrityAssessment:
    """Read-only guard for BHD5 salted hashes affected by a patch plan.

    The hashes cover selected ranges of the encrypted bytes stored in the BDT,
    not the decrypted logical file.  Validate the complete current BDT baseline
    first, then overlay the prepared writes in memory and reject a plan that
    would make any declared digest stale.  ``strict`` is deliberately the
    default and rejects every planned authenticated-range divergence.  The
    explicit ``scoped_mod`` mode records only the divergences caused by this
    exact plan so that staging can later prove the set did not grow.  A corrupt
    or already modified baseline is always rejected in both modes.

    Nothing is written by this function.
    """

    selected_mode = _validated_bhd_integrity_mode(mode)
    external_wem_ids = _planned_external_wem_ids(plan)
    validated_entry_count = 0
    divergent_entries: set[BHDEntryIdentity] = set()

    writes_by_archive: dict[Path, list[PreparedWrite]] = {}
    for write in plan.writes:
        if sha256_file(write.replacement.source_path) != write.source_sha256:
            raise PatcherError(
                "Il payload è cambiato durante la verifica di integrità: "
                f"{write.replacement.source_relative}. Nessun file è stato modificato."
            )
        writes_by_archive.setdefault(write.target.archive.bdt_path, []).append(write)

    archive_by_path: dict[Path, Archive] = {}
    selected_archives = (
        tuple(archives)
        if archives is not None
        else tuple(items[0].target.archive for items in writes_by_archive.values())
    )
    for archive in selected_archives:
        previous = archive_by_path.get(archive.bdt_path)
        if previous is not None:
            raise CompatibilityError(
                f"Archivio duplicato nella verifica SHA: {archive.bdt_path.name}."
            )
        archive_by_path[archive.bdt_path] = archive
    for archive_path, archive_writes in writes_by_archive.items():
        archive = archive_by_path.get(archive_path)
        if archive is None:
            raise CompatibilityError(
                f"Il piano fa riferimento a un archivio non coperto dalla verifica: "
                f"{archive_path.name}."
            )
        if any(item.target.archive != archive for item in archive_writes):
            raise CompatibilityError(
                f"Il piano ha metadati divergenti per {archive_path.name}. "
                "Nessun file è stato modificato."
            )

    archive_paths = set(archive_by_path)
    if baseline_paths is not None:
        missing = archive_paths.difference(baseline_paths)
        extra = set(baseline_paths).difference(archive_paths)
        if missing or extra:
            raise CompatibilityError(
                "Mappatura inesatta dei baseline per la verifica SHA "
                f"(mancanti={sorted(path.name for path in missing)}, "
                f"in più={sorted(path.name for path in extra)})."
            )
        selected_paths = tuple(baseline_paths[path] for path in archive_by_path)
        if len(set(selected_paths)) != len(selected_paths):
            raise CompatibilityError(
                "Due archivi puntano allo stesso baseline nella verifica SHA."
            )
        if any(
            baseline_paths[archive_path] == archive_path
            for archive_path in archive_by_path
        ):
            raise CompatibilityError(
                "Il baseline immutabile non può essere il BDT attivo nella verifica SHA."
            )

    for archive_path, archive in archive_by_path.items():
        archive_writes = writes_by_archive.get(archive_path, ())
        read_path = (
            archive_path
            if baseline_paths is None
            else baseline_paths[archive_path]
        )

        intervals = sorted(
            (
                (
                    write.target.entry.file_offset,
                    write.target.entry.file_offset
                    + write.target.entry.padded_file_size,
                    write,
                )
                for write in archive_writes
            ),
            key=lambda item: item[0],
        )
        previous_end = -1
        for start, end, write in intervals:
            if start < previous_end:
                raise CompatibilityError(
                    f"Il piano ha scritture sovrapposte in {archive_path.name}: "
                    f"{write.replacement.source_relative}. Nessun file è stato modificato."
                )
            previous_end = end
        write_starts = [item[0] for item in intervals]
        write_ends = [item[1] for item in intervals]

        stream, opened = _open_bdt_for_integrity(
            read_path,
            expected_size=archive.bdt_size,
            label=f"Il baseline di {archive_path.name}",
        )
        try:
            if (
                baseline_paths is None
                and opened.st_mtime_ns != archive.bdt_mtime_ns
            ):
                raise CompatibilityError(
                    f"{archive_path.name} è cambiato dopo la pianificazione; riprova. "
                    "Nessun file è stato modificato."
                )

            # Materialize every dynamic BNK up front.  A BNK whose bytes happen
            # to sit outside all declared SHA ranges must still be proven
            # mergeable before a backup is published or staging begins.
            if merge_bnk_from_baseline:
                for _write_index, (_start, _end, write) in enumerate(intervals):
                    if write.replacement.source_path.suffix.lower() != ".bnk":
                        continue
                    source_data = write.replacement.source_path.read_bytes()
                    if hashlib.sha256(source_data).hexdigest() != write.source_sha256:
                        raise PatcherError(
                            "Il payload è cambiato durante la verifica di integrità: "
                            f"{write.replacement.source_relative}. Nessun file è stato modificato."
                        )
                    _materialize_prepared_slot(
                        source_data,
                        write.replacement.source_path.suffix,
                        write.target.entry,
                        baseline_stream=stream,
                        archive_name=archive_path.name,
                        external_wem_ids=external_wem_ids,
                        merge_bnk_from_baseline=True,
                    )

            for entry_index, entry in enumerate(archive.entries):
                sha_info = entry.sha_info
                if sha_info is None:
                    if require_entry_sha_metadata:
                        raise CompatibilityError(
                            f"Voce senza SHA salted in {archive_path.name}: "
                            f"0x{entry.file_name_hash:016x}. La modalità strutturale richiede "
                            "l'integrità di tutte le voci. Nessun file è stato modificato."
                        )
                    continue
                if require_entry_sha_metadata and not any(
                    item.start_offset >= 0 and item.end_offset > item.start_offset
                    for item in sha_info.ranges
                ):
                    raise CompatibilityError(
                        f"Voce senza un range SHA utilizzabile in {archive_path.name}: "
                        f"0x{entry.file_name_hash:016x}. La modalità strutturale richiede "
                        "l'integrità di tutte le voci. Nessun file è stato modificato."
                    )
                validated_entry_count += 1
                if len(sha_info.hash_bytes) != hashlib.sha256().digest_size:
                    raise CompatibilityError(
                        f"Metadato SHA non valido in {archive_path.name}, voce "
                        f"0x{entry.file_name_hash:016x}. Nessun file è stato modificato."
                    )

                current_digest = hashlib.sha256()
                planned_digest = hashlib.sha256()
                changed_by: str | None = None
                # Keep at most the prepared writes overlapping this one BHD
                # entry.  The production payload is hundreds of MiB; caching
                # the complete normalized tree would create an avoidable RAM
                # spike during the read-only guard.
                prepared_cache: dict[int, bytes] = {}
                for range_index, item in enumerate(sha_info.ranges):
                    if item.start_offset == -1 or item.end_offset == -1:
                        continue
                    if (
                        item.start_offset < 0
                        or item.end_offset < item.start_offset
                        or item.end_offset > entry.padded_file_size
                    ):
                        raise CompatibilityError(
                            f"Range SHA[{range_index}] non valido in {archive_path.name}, "
                            f"voce 0x{entry.file_name_hash:016x}. "
                            "Nessun file è stato modificato."
                        )

                    absolute = entry.file_offset + item.start_offset
                    range_end = entry.file_offset + item.end_offset
                    while absolute < range_end:
                        length = min(COPY_BUFFER_SIZE, range_end - absolute)
                        stream.seek(absolute)
                        current_chunk = stream.read(length)
                        if len(current_chunk) != length:
                            raise CompatibilityError(
                                f"Lettura incompleta di {archive_path.name} nella voce "
                                f"0x{entry.file_name_hash:016x}. "
                                "Nessun file è stato modificato."
                            )
                        planned_chunk = bytearray(current_chunk)
                        chunk_end = absolute + length
                        write_index = bisect.bisect_right(write_ends, absolute)
                        while (
                            write_index < len(intervals)
                            and write_starts[write_index] < chunk_end
                        ):
                            write_start, write_end, write = intervals[write_index]
                            overlap_start = max(absolute, write_start)
                            overlap_end = min(chunk_end, write_end)
                            if overlap_start < overlap_end:
                                prepared = prepared_cache.get(write_index)
                                if prepared is None:
                                    source_data = write.replacement.source_path.read_bytes()
                                    if (
                                        hashlib.sha256(source_data).hexdigest()
                                        != write.source_sha256
                                    ):
                                        raise PatcherError(
                                            "Il payload è cambiato durante la verifica di "
                                            f"integrità: {write.replacement.source_relative}. "
                                            "Nessun file è stato modificato."
                                        )
                                    prepared = _materialize_prepared_slot(
                                        source_data,
                                        write.replacement.source_path.suffix,
                                        write.target.entry,
                                        baseline_stream=stream,
                                        archive_name=archive_path.name,
                                        external_wem_ids=external_wem_ids,
                                        merge_bnk_from_baseline=(
                                            merge_bnk_from_baseline
                                        ),
                                    )
                                    del source_data
                                    prepared_cache[write_index] = prepared
                                destination_start = overlap_start - absolute
                                source_start = overlap_start - write_start
                                replacement = prepared[
                                    source_start : source_start
                                    + (overlap_end - overlap_start)
                                ]
                                destination_end = destination_start + len(replacement)
                                if (
                                    planned_chunk[destination_start:destination_end]
                                    != replacement
                                ):
                                    changed_by = (
                                        changed_by
                                        or write.replacement.source_relative
                                    )
                                    planned_chunk[
                                        destination_start:destination_end
                                    ] = replacement
                            write_index += 1

                        current_digest.update(current_chunk)
                        planned_digest.update(planned_chunk)
                        absolute = chunk_end

                current_digest.update(archive.salt)
                planned_digest.update(archive.salt)
                if current_digest.digest() != sha_info.hash_bytes:
                    raise CompatibilityError(
                        f"Integrità SHA salted non valida in {archive_path.name}, voce "
                        f"0x{entry.file_name_hash:016x}: il BDT attuale non corrisponde al "
                        "BHD. Nessun file è stato modificato."
                    )
                if planned_digest.digest() != sha_info.hash_bytes:
                    if changed_by is None:
                        raise CompatibilityError(
                            f"La simulazione SHA è divergita senza una scrittura "
                            f"corrispondente in {archive_path.name}, voce "
                            f"0x{entry.file_name_hash:016x}. Nessun file è stato modificato."
                        )
                    identity = _bhd_entry_identity(archive, entry_index, entry)
                    divergent_entries.add(identity)
                    if selected_mode == BHD_INTEGRITY_STRICT:
                        raise CompatibilityError(
                            f"La patch modificherebbe un range SHA autenticato in "
                            f"{archive_path.name}, voce 0x{entry.file_name_hash:016x} "
                            f"({changed_by}). L'installazione diretta non è sicura per questo "
                            "build. Nessun file è stato modificato."
                        )

            _require_open_bdt_unchanged(
                read_path,
                stream,
                opened,
                expected_size=archive.bdt_size,
                label=f"Il baseline di {archive_path.name}",
            )
        finally:
            stream.close()

    return BHDIntegrityAssessment(
        validated_entry_count=validated_entry_count,
        divergent_entries=frozenset(divergent_entries),
    )


def _open_bdt_for_integrity(
    path: Path,
    *,
    expected_size: int,
    label: str,
) -> tuple[BinaryIO, os.stat_result]:
    try:
        before = path.lstat()
    except OSError as exc:
        raise CompatibilityError(f"Impossibile aprire {label}: {exc}.") from exc
    if (
        _metadata_is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size != expected_size
    ):
        raise CompatibilityError(
            f"{label} non è un file regolare esclusivo con la dimensione attesa."
        )
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise CompatibilityError(f"Impossibile leggere {label}: {exc}.") from exc
    opened = os.fstat(stream.fileno())
    if (
        not stat.S_ISREG(opened.st_mode)
        or opened.st_nlink != 1
        or opened.st_size != expected_size
        or (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino)
        or opened.st_mtime_ns != before.st_mtime_ns
        # Windows may expose different ctime semantics for path and handle
        # snapshots.  POSIX ctime is comparable across both views.
        or (
            os.name != "nt"
            and getattr(opened, "st_ctime_ns", None)
            != getattr(before, "st_ctime_ns", None)
        )
    ):
        stream.close()
        raise CompatibilityError(f"{label} è cambiato durante l'apertura.")
    return stream, opened


def _require_open_bdt_unchanged(
    path: Path,
    stream: BinaryIO,
    opened: os.stat_result,
    *,
    expected_size: int,
    label: str,
) -> None:
    opened_after = os.fstat(stream.fileno())
    try:
        current = path.lstat()
    except OSError as exc:
        raise CompatibilityError(f"{label} è scomparso durante la verifica: {exc}.") from exc
    if (
        _metadata_is_link_or_reparse(current)
        or not stat.S_ISREG(current.st_mode)
        or current.st_nlink != 1
        or current.st_size != expected_size
        or opened_after.st_size != expected_size
        or opened_after.st_mtime_ns != opened.st_mtime_ns
        or current.st_mtime_ns != opened.st_mtime_ns
        or getattr(opened_after, "st_ctime_ns", None)
        != getattr(opened, "st_ctime_ns", None)
        or (
            os.name != "nt"
            and getattr(current, "st_ctime_ns", None)
            != getattr(opened, "st_ctime_ns", None)
        )
        or (opened_after.st_dev, opened_after.st_ino)
        != (opened.st_dev, opened.st_ino)
        or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino)
    ):
        raise CompatibilityError(f"{label} è cambiato durante la verifica.")


def _streamed_bhd_entry_sha256(
    stream: BinaryIO,
    archive: Archive,
    entry: FileEntry,
) -> bytes:
    sha_info = entry.sha_info
    if sha_info is None:
        raise ValueError("La voce non ha metadati SHA.")
    if len(sha_info.hash_bytes) != hashlib.sha256().digest_size:
        raise CompatibilityError(
            f"Metadato SHA non valido in {archive.bdt_path.name}, voce "
            f"0x{entry.file_name_hash:016x}."
        )
    digest = hashlib.sha256()
    for range_index, item in enumerate(sha_info.ranges):
        if item.start_offset == -1 or item.end_offset == -1:
            continue
        if (
            item.start_offset < 0
            or item.end_offset < item.start_offset
            or item.end_offset > entry.padded_file_size
        ):
            raise CompatibilityError(
                f"Range SHA[{range_index}] non valido in {archive.bdt_path.name}, "
                f"voce 0x{entry.file_name_hash:016x}."
            )
        absolute = entry.file_offset + item.start_offset
        remaining = item.end_offset - item.start_offset
        stream.seek(absolute)
        while remaining:
            chunk = stream.read(min(COPY_BUFFER_SIZE, remaining))
            if not chunk:
                raise CompatibilityError(
                    f"Lettura incompleta di {archive.bdt_path.name}, voce "
                    f"0x{entry.file_name_hash:016x}."
                )
            digest.update(chunk)
            remaining -= len(chunk)
    digest.update(archive.salt)
    return digest.digest()


def _require_equal_stream_range(
    expected_stream: BinaryIO,
    actual_stream: BinaryIO,
    *,
    start: int,
    end: int,
    archive_name: str,
    actual_bytes: Callable[[bytes], object] | None = None,
) -> None:
    if start >= end:
        return
    expected_stream.seek(start)
    actual_stream.seek(start)
    cursor = start
    while cursor < end:
        length = min(COPY_BUFFER_SIZE, end - cursor)
        expected = expected_stream.read(length)
        actual = actual_stream.read(length)
        if len(expected) != length or len(actual) != length:
            raise CompatibilityError(
                f"Lettura incompleta durante la verifica dello staging di {archive_name}."
            )
        if actual != expected:
            mismatch = next(
                index
                for index, (left, right) in enumerate(zip(expected, actual, strict=True))
                if left != right
            )
            raise CompatibilityError(
                f"Lo staging di {archive_name} contiene modifiche fuori dagli slot "
                f"pianificati (spillover all'offset {cursor + mismatch})."
            )
        if actual_bytes is not None:
            actual_bytes(actual)
        cursor += length


def validate_staged_patch_sha_integrity(
    plan: PatchPlan,
    archives: Sequence[Archive],
    *,
    baseline_paths: Mapping[Path, Path],
    staging_paths: Mapping[Path, Path],
    expected_divergent_entries: AbstractSet[BHDEntryIdentity],
    staging_identities: Mapping[Path, tuple[int, int]] | None = None,
    merge_bnk_from_baseline: bool = False,
    require_entry_sha_metadata: bool = False,
) -> BHDIntegrityAssessment:
    """Prove that staging is exactly baseline plus this plan, with no spillover.

    The pristine backup is authenticated again and therefore cannot be waived by
    ``scoped_mod``.  The resulting staged BHD divergences must equal, not merely
    contain, the set produced by :func:`validate_patch_plan_sha_integrity`.
    """

    expected_divergences = frozenset(expected_divergent_entries)
    external_wem_ids = _planned_external_wem_ids(plan)
    if any(not isinstance(item, BHDEntryIdentity) for item in expected_divergences):
        raise TypeError("expected_divergent_entries deve contenere BHDEntryIdentity.")

    archive_by_path: dict[Path, Archive] = {}
    for archive in archives:
        if archive.bdt_path in archive_by_path:
            raise CompatibilityError(
                f"Archivio duplicato nella verifica dello staging: {archive.bdt_path.name}."
            )
        archive_by_path[archive.bdt_path] = archive

    writes_by_archive: dict[Path, list[PreparedWrite]] = {
        path: [] for path in archive_by_path
    }
    for write in plan.writes:
        live_path = write.target.archive.bdt_path
        archive = archive_by_path.get(live_path)
        if archive is None or archive != write.target.archive:
            raise CompatibilityError(
                f"Lo staging non copre i metadati pianificati di {live_path.name}."
            )
        writes_by_archive[live_path].append(write)

    expected_paths = set(archive_by_path)
    missing_baselines = expected_paths.difference(baseline_paths)
    missing_staging = expected_paths.difference(staging_paths)
    extra_baselines = set(baseline_paths).difference(expected_paths)
    extra_staging = set(staging_paths).difference(expected_paths)
    missing_identities = (
        expected_paths.difference(staging_identities)
        if staging_identities is not None
        else set()
    )
    extra_identities = (
        set(staging_identities).difference(expected_paths)
        if staging_identities is not None
        else set()
    )
    if (
        missing_baselines
        or missing_staging
        or extra_baselines
        or extra_staging
        or missing_identities
        or extra_identities
    ):
        missing = sorted(
            path.name
            for path in missing_baselines.union(missing_staging, missing_identities)
        )
        extra = sorted(
            path.name
            for path in extra_baselines.union(extra_staging, extra_identities)
        )
        raise CompatibilityError(
            "Mappatura inesatta per verificare lo staging "
            f"(mancanti={missing}, in più={extra})."
        )

    validated_entry_count = 0
    actual_divergences: set[BHDEntryIdentity] = set()
    known_identities: set[BHDEntryIdentity] = set()
    validated_archive_sha256: dict[Path, str] = {}
    validated_archive_identities: dict[Path, tuple[int, int]] = {}

    for live_path, archive in archive_by_path.items():
        baseline_path = baseline_paths[live_path]
        stage_path = staging_paths[live_path]
        if baseline_path == stage_path:
            raise CompatibilityError(
                f"Baseline e staging di {live_path.name} puntano allo stesso percorso."
            )
        baseline_stream, baseline_opened = _open_bdt_for_integrity(
            baseline_path,
            expected_size=archive.bdt_size,
            label=f"Il baseline di {live_path.name}",
        )
        try:
            stage_stream, stage_opened = _open_bdt_for_integrity(
                stage_path,
                expected_size=archive.bdt_size,
                label=f"Lo staging di {live_path.name}",
            )
        except Exception:
            baseline_stream.close()
            raise
        try:
            if (baseline_opened.st_dev, baseline_opened.st_ino) == (
                stage_opened.st_dev,
                stage_opened.st_ino,
            ):
                raise CompatibilityError(
                    f"Baseline e staging di {live_path.name} sono lo stesso file."
                )
            if staging_identities is not None:
                expected_identity = staging_identities.get(live_path)
                if expected_identity is None or expected_identity != (
                    stage_opened.st_dev,
                    stage_opened.st_ino,
                ):
                    raise CompatibilityError(
                        f"Lo staging di {live_path.name} è stato sostituito prima della verifica."
                    )

            ordered_writes = sorted(
                writes_by_archive.get(live_path, ()),
                key=lambda item: item.target.entry.file_offset,
            )
            stage_digest = hashlib.sha256()
            cursor = 0
            for write in ordered_writes:
                entry = write.target.entry
                start = entry.file_offset
                end = start + entry.padded_file_size
                if start < cursor or end > archive.bdt_size:
                    raise CompatibilityError(
                        f"Slot sovrapposti o fuori dal file in {live_path.name}."
                    )
                _require_equal_stream_range(
                    baseline_stream,
                    stage_stream,
                    start=cursor,
                    end=start,
                    archive_name=live_path.name,
                    actual_bytes=stage_digest.update,
                )
                source_data = write.replacement.source_path.read_bytes()
                if hashlib.sha256(source_data).hexdigest() != write.source_sha256:
                    raise PatcherError(
                        "Il payload è cambiato prima della verifica dello staging: "
                        f"{write.replacement.source_relative}."
                    )
                expected_slot = _materialize_prepared_slot(
                    source_data,
                    write.replacement.source_path.suffix,
                    entry,
                    baseline_stream=baseline_stream,
                    archive_name=live_path.name,
                    external_wem_ids=external_wem_ids,
                    merge_bnk_from_baseline=merge_bnk_from_baseline,
                )
                stage_stream.seek(start)
                actual_slot = stage_stream.read(len(expected_slot))
                if actual_slot != expected_slot:
                    raise CompatibilityError(
                        f"Lo staging di {live_path.name} diverge nello slot pianificato "
                        f"{write.replacement.source_relative}."
                    )
                stage_digest.update(actual_slot)
                cursor = end
            _require_equal_stream_range(
                baseline_stream,
                stage_stream,
                start=cursor,
                end=archive.bdt_size,
                archive_name=live_path.name,
                actual_bytes=stage_digest.update,
            )

            for entry_index, entry in enumerate(archive.entries):
                if entry.sha_info is None:
                    if require_entry_sha_metadata:
                        raise CompatibilityError(
                            f"Voce senza SHA salted nel baseline di {live_path.name}: "
                            f"0x{entry.file_name_hash:016x}."
                        )
                    continue
                if require_entry_sha_metadata and not any(
                    item.start_offset >= 0 and item.end_offset > item.start_offset
                    for item in entry.sha_info.ranges
                ):
                    raise CompatibilityError(
                        f"Voce senza un range SHA utilizzabile nel baseline di "
                        f"{live_path.name}: 0x{entry.file_name_hash:016x}."
                    )
                validated_entry_count += 1
                identity = _bhd_entry_identity(archive, entry_index, entry)
                known_identities.add(identity)
                baseline_digest = _streamed_bhd_entry_sha256(
                    baseline_stream, archive, entry
                )
                if baseline_digest != entry.sha_info.hash_bytes:
                    raise CompatibilityError(
                        f"Baseline non valido in {live_path.name}, voce "
                        f"0x{entry.file_name_hash:016x}: il backup non corrisponde al BHD."
                    )
                stage_entry_digest = _streamed_bhd_entry_sha256(
                    stage_stream, archive, entry
                )
                if stage_entry_digest != entry.sha_info.hash_bytes:
                    actual_divergences.add(identity)

            _require_open_bdt_unchanged(
                baseline_path,
                baseline_stream,
                baseline_opened,
                expected_size=archive.bdt_size,
                label=f"Il baseline di {live_path.name}",
            )
            _require_open_bdt_unchanged(
                stage_path,
                stage_stream,
                stage_opened,
                expected_size=archive.bdt_size,
                label=f"Lo staging di {live_path.name}",
            )
            validated_archive_sha256[live_path] = stage_digest.hexdigest()
            validated_archive_identities[live_path] = (
                stage_opened.st_dev,
                stage_opened.st_ino,
            )
        finally:
            baseline_stream.close()
            stage_stream.close()

    unknown_expected = expected_divergences.difference(known_identities)
    if unknown_expected:
        raise CompatibilityError(
            "L'insieme atteso di divergenze SHA fa riferimento a voci fuori dallo staging."
        )
    actual = frozenset(actual_divergences)
    if actual != expected_divergences:
        unexpected = actual.difference(expected_divergences)
        missing = expected_divergences.difference(actual)
        raise CompatibilityError(
            "L'insieme SHA dello staging diverge dal piano "
            f"(inattese={len(unexpected)}, mancanti={len(missing)}); "
            "possibile spillover."
        )
    return BHDIntegrityAssessment(
        validated_entry_count=validated_entry_count,
        divergent_entries=actual,
        validated_archive_sha256=tuple(
            sorted(validated_archive_sha256.items(), key=lambda item: str(item[0]))
        ),
        validated_archive_identities=tuple(
            sorted(
                validated_archive_identities.items(),
                key=lambda item: str(item[0]),
            )
        ),
    )


def parse_bhd5(data: bytes, bdt_size: int | None = None) -> tuple[FileEntry, ...]:
    """Le as entradas necessarias de um BHD5 com validacao de limites."""

    data, _salt = _validated_bhd5_data_and_salt(data)

    bucket_count = _read_i32(data, 16, "bucket_count")
    buckets_offset = _read_i32(data, 20, "buckets_offset")
    if bucket_count < 0 or bucket_count > 1_000_000:
        raise CompatibilityError(f"BHD non valido: bucket_count={bucket_count}.")
    if buckets_offset < 28 + len(_salt):
        raise CompatibilityError("BHD non valido: buckets_offset si sovrappone al salt.")
    _require_slice(data, buckets_offset, bucket_count * 8, "tabella dei bucket")

    entries: list[FileEntry] = []
    for bucket_index in range(bucket_count):
        bucket_pos = buckets_offset + bucket_index * 8
        entry_count = _read_i32(data, bucket_pos, "entry_count")
        entries_offset = _read_i32(data, bucket_pos + 4, "entries_offset")
        if entry_count < 0 or entry_count > 10_000_000:
            raise CompatibilityError(
                f"BHD non valido: entry_count={entry_count} nel bucket {bucket_index}."
            )
        _require_slice(data, entries_offset, entry_count * 40, "tabella delle voci")

        for entry_index in range(entry_count):
            pos = entries_offset + entry_index * 40
            file_hash = _read_u64(data, pos, "file_name_hash")
            padded = _read_i32(data, pos + 8, "padded_file_size")
            unpadded = _read_i32(data, pos + 12, "unpadded_file_size")
            file_offset = _read_i64(data, pos + 16, "file_offset")
            sha_offset = _read_i64(data, pos + 24, "sha_hash_offset")
            aes_offset = _read_i64(data, pos + 32, "aes_key_offset")

            sizes_are_zero = padded == 0 and unpadded == 0
            if (
                padded < 0
                or unpadded < 0
                or (padded == 0) != (unpadded == 0)
                or (not sizes_are_zero and unpadded > padded)
                or file_offset < 0
                or sha_offset < 0
                or aes_offset < 0
            ):
                raise CompatibilityError(
                    "BHD non valido: dimensioni/offset incoerenti nella voce "
                    f"{entry_index} del bucket {bucket_index}."
                )
            if bdt_size is not None and file_offset + padded > bdt_size:
                raise CompatibilityError(
                    "BHD e BDT non corrispondono: la voce termina oltre il BDT "
                    f"({file_offset + padded} > {bdt_size})."
                )

            aes_info = None
            if aes_offset > 0:
                _require_slice(data, aes_offset, 20, "AES info")
                key = data[aes_offset : aes_offset + 16]
                ranges = _read_ranges(
                    data,
                    aes_offset + 16,
                    padded,
                    "AES ranges",
                    block_size=16,
                )
                aes_info = AESKeyInfo(key=key, ranges=ranges)

            sha_info = None
            if sha_offset > 0:
                _require_slice(data, sha_offset, 36, "SHA info")
                digest = data[sha_offset : sha_offset + 32]
                ranges = _read_ranges(data, sha_offset + 32, padded, "SHA ranges")
                sha_info = SHAHashInfo(hash_bytes=digest, ranges=ranges)

            entries.append(
                FileEntry(
                    file_name_hash=file_hash,
                    padded_file_size=padded,
                    unpadded_file_size=unpadded,
                    file_offset=file_offset,
                    sha_hash_offset=sha_offset,
                    aes_key_offset=aes_offset,
                    sha_info=sha_info,
                    aes_info=aes_info,
                )
            )
    return tuple(entries)


def hash_path(path: str) -> int:
    value = 0
    normalized = path.replace("\\", "/").strip("/").lower()
    for character in "/" + normalized:
        value = (value * 0x85 + ord(character)) & 0xFFFFFFFFFFFFFFFF
    return value


def _riff_chunks(wem_data: bytes) -> tuple[bytes, bytes]:
    if len(wem_data) < 12 or wem_data[:4] != b"RIFF" or wem_data[8:12] != b"WAVE":
        raise CompatibilityError("WEM non valido: intestazione RIFF/WAVE assente.")
    fmt_data: bytes | None = None
    audio_data: bytes | None = None
    pos = 12
    while pos + 8 <= len(wem_data):
        chunk_id = wem_data[pos : pos + 4]
        chunk_size = struct.unpack_from("<I", wem_data, pos + 4)[0]
        content_start = pos + 8
        content_end = content_start + chunk_size
        if content_end > len(wem_data):
            raise CompatibilityError("WEM non valido: il chunk supera la fine del file.")
        if chunk_id == b"fmt " and fmt_data is None:
            fmt_data = wem_data[content_start:content_end]
        elif chunk_id == b"data" and audio_data is None:
            audio_data = wem_data[content_start:content_end]
        pos = content_end + (chunk_size & 1)
    if fmt_data is None or audio_data is None:
        raise CompatibilityError("WEM non valido: chunk fmt/data assenti.")
    return fmt_data, audio_data


def normalize_wem(wem_data: bytes, target_size: int) -> bytes:
    """Rimuove i chunk ausiliari e occupa esattamente la dimensione logica dello slot."""
    fmt_data, audio_data = _riff_chunks(wem_data)
    fmt_padding = len(fmt_data) & 1
    header_size = 12 + 8 + len(fmt_data) + fmt_padding + 8
    minimum_size = header_size + len(audio_data)
    if minimum_size > target_size:
        raise CompatibilityError(
            f"WEM più grande dello slot logico ({minimum_size} > {target_size}); "
            "il file non verrà troncato."
        )
    data_size = target_size - header_size
    result = bytearray()
    result.extend(b"RIFF")
    result.extend(struct.pack("<I", target_size - 8))
    result.extend(b"WAVEfmt ")
    result.extend(struct.pack("<I", len(fmt_data)))
    result.extend(fmt_data)
    if fmt_padding:
        result.append(0)
    result.extend(b"data")
    result.extend(struct.pack("<I", data_size))
    result.extend(audio_data)
    result.extend(b"\0" * (data_size - len(audio_data)))
    if len(result) != target_size:  # difesa contro regressioni nell'assemblaggio RIFF
        raise AssertionError(f"WEM normalizzato con dimensione errata: {len(result)}.")
    return bytes(result)


def encrypt_aes_ecb(
    data: bytearray, key: bytes, ranges: Sequence[AESRange]
) -> bytearray:
    if len(key) != 16:
        raise CompatibilityError(f"Chiave AES non valida ({len(key)} byte).")
    for item in ranges:
        if item.start_offset == -1 or item.end_offset == -1:
            continue
        if (
            item.start_offset < 0
            or item.end_offset < item.start_offset
            or item.end_offset > len(data)
        ):
            raise CompatibilityError("Range AES fuori dallo slot di destinazione.")
        if (item.end_offset - item.start_offset) % 16:
            raise CompatibilityError("Il range AES deve avere dimensione multipla di 16 byte.")

    try:
        from Crypto.Cipher import AES
    except ImportError as exc:  # pragma: no cover - dipende dall'installazione locale
        raise PatcherError(
            "Dipendenza PyCryptodome mancante. Esegui di nuovo ERITA.cmd."
        ) from exc
    cipher = AES.new(key, AES.MODE_ECB)
    for item in ranges:
        if item.start_offset == -1 or item.end_offset == -1:
            continue
        length = item.end_offset - item.start_offset
        if length:
            start = item.start_offset
            data[start : start + length] = cipher.encrypt(
                bytes(data[start : start + length])
            )
    return data


def decrypt_aes_ecb(
    data: bytearray, key: bytes, ranges: Sequence[AESRange]
) -> bytearray:
    """Decrypt the BHD-declared ranges of one complete BDT slot in place."""

    if len(key) != 16:
        raise CompatibilityError(f"Chiave AES non valida ({len(key)} byte).")
    for item in ranges:
        if item.start_offset == -1 or item.end_offset == -1:
            continue
        if (
            item.start_offset < 0
            or item.end_offset < item.start_offset
            or item.end_offset > len(data)
        ):
            raise CompatibilityError("Range AES fora do slot de origem.")
        if (item.end_offset - item.start_offset) % 16:
            raise CompatibilityError("Il range AES deve avere dimensione multipla di 16 byte.")

    try:
        from Crypto.Cipher import AES
    except ImportError as exc:  # pragma: no cover - dipende dall'installazione locale
        raise PatcherError(
            "Dipendenza PyCryptodome assente. Esegui di nuovo ERITA.cmd."
        ) from exc
    cipher = AES.new(key, AES.MODE_ECB)
    for item in ranges:
        if item.start_offset == -1 or item.end_offset == -1:
            continue
        length = item.end_offset - item.start_offset
        if length:
            start = item.start_offset
            data[start : start + length] = cipher.decrypt(
                bytes(data[start : start + length])
            )
    return data


def prepare_slot(source_data: bytes, source_suffix: str, entry: FileEntry) -> bytes:
    suffix = source_suffix.lower()
    if suffix == ".wem":
        logical = normalize_wem(source_data, entry.unpadded_file_size)
    elif suffix == ".bnk":
        if len(source_data) > entry.unpadded_file_size:
            raise CompatibilityError(
                f"BNK più grande dello slot logico ({len(source_data)} > "
                f"{entry.unpadded_file_size})."
            )
        logical = source_data + b"\0" * (entry.unpadded_file_size - len(source_data))
    else:
        raise CompatibilityError(f"Estensione di payload non consentita: {source_suffix}.")

    if len(logical) > entry.padded_file_size:
        raise CompatibilityError(
            f"File più grande dello slot fisico ({len(logical)} > {entry.padded_file_size})."
        )
    result = bytearray(logical)
    result.extend(b"\0" * (entry.padded_file_size - len(result)))
    if entry.aes_info and entry.aes_info.ranges:
        encrypt_aes_ecb(result, entry.aes_info.key, entry.aes_info.ranges)
    return bytes(result)


def prepare_bnk_slot_from_baseline(
    source_data: bytes,
    encrypted_baseline_slot: bytes,
    entry: FileEntry,
    *,
    external_wem_ids: AbstractSet[int],
) -> bytes:
    """Merge a payload BNK into the decrypted vanilla staging-slot baseline."""

    if len(encrypted_baseline_slot) != entry.padded_file_size:
        raise CompatibilityError(
            "Lettura incompleta dello slot BNK vanilla "
            f"({len(encrypted_baseline_slot)}/{entry.padded_file_size} bytes)."
        )
    baseline = bytearray(encrypted_baseline_slot)
    if entry.aes_info and entry.aes_info.ranges:
        decrypt_aes_ecb(baseline, entry.aes_info.key, entry.aes_info.ranges)
    vanilla = bytes(baseline[: entry.unpadded_file_size])
    try:
        merged = merge_bnk_with_vanilla(
            vanilla,
            source_data,
            external_wem_ids=external_wem_ids,
        )
    except BnkMergeError as exc:
        raise CompatibilityError(f"Impossibile unire il BNK con il vanilla: {exc}") from exc
    return prepare_slot(merged, ".bnk", entry)


def _materialize_prepared_slot(
    source_data: bytes,
    source_suffix: str,
    entry: FileEntry,
    *,
    baseline_stream: BinaryIO | None,
    archive_name: str,
    external_wem_ids: AbstractSet[int],
    merge_bnk_from_baseline: bool,
) -> bytes:
    """Build the exact encrypted slot bytes used by every validation phase.

    In structural compatibility mode a BNK is never copied wholesale.  It is
    merged over the immutable vanilla slot belonging to the target build.  All
    callers (SHA simulation, staging write and staging verification) use this
    one helper so none of those phases can disagree about the authorized bytes.
    """

    if source_suffix.lower() != ".bnk" or not merge_bnk_from_baseline:
        return prepare_slot(source_data, source_suffix, entry)
    if baseline_stream is None:
        raise CompatibilityError(
            f"Baseline mancante per unire i BNK in {archive_name}."
        )
    baseline_stream.seek(entry.file_offset)
    encrypted_baseline_slot = baseline_stream.read(entry.padded_file_size)
    if len(encrypted_baseline_slot) != entry.padded_file_size:
        raise CompatibilityError(
            f"Lettura incompleta del baseline di {archive_name} per lo slot BNK "
            f"0x{entry.file_name_hash:016x}."
        )
    return prepare_bnk_slot_from_baseline(
        source_data,
        encrypted_baseline_slot,
        entry,
        external_wem_ids=external_wem_ids,
    )


def _optional_stat_field_unchanged(
    before: os.stat_result,
    after: os.stat_result,
    field: str,
) -> bool:
    """Compare one timestamp when both filesystem snapshots expose it."""

    before_value = getattr(before, field, None)
    after_value = getattr(after, field, None)
    return (
        before_value is None
        or after_value is None
        or before_value == after_value
    )


def _regular_hash_open_snapshot_is_valid(
    before: os.stat_result,
    opened: os.stat_result,
) -> bool:
    """Bind a newly opened hash stream to the exact path snapshot inspected."""

    return (
        stat.S_ISREG(opened.st_mode)
        and opened.st_nlink == 1
        and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino)
        and opened.st_size == before.st_size
        and opened.st_mtime_ns == before.st_mtime_ns
        # Windows can expose different ctime semantics through path and handle
        # snapshots. Compare each view longitudinally below; POSIX can also bind
        # the two initial views directly.
        and (
            os.name == "nt"
            or _optional_stat_field_unchanged(before, opened, "st_ctime_ns")
        )
    )


def _regular_hash_final_snapshot_is_valid(
    before: os.stat_result,
    opened: os.stat_result,
    opened_after: os.stat_result,
    current: os.stat_result,
    *,
    bytes_read: int,
) -> bool:
    """Prove a hash consumed one unchanged regular file through exact EOF."""

    identity = (before.st_dev, before.st_ino)
    expected_size = before.st_size
    return (
        stat.S_ISREG(opened_after.st_mode)
        and stat.S_ISREG(current.st_mode)
        and not _metadata_is_link_or_reparse(current)
        and opened_after.st_nlink == 1
        and current.st_nlink == 1
        and (opened_after.st_dev, opened_after.st_ino) == identity
        and (current.st_dev, current.st_ino) == identity
        and opened_after.st_size == expected_size
        and current.st_size == expected_size
        and bytes_read == expected_size
        and opened_after.st_mtime_ns == opened.st_mtime_ns
        and current.st_mtime_ns == before.st_mtime_ns
        and _optional_stat_field_unchanged(opened, opened_after, "st_ctime_ns")
        and _optional_stat_field_unchanged(before, current, "st_ctime_ns")
        and (
            os.name == "nt"
            or _optional_stat_field_unchanged(
                opened_after,
                current,
                "st_ctime_ns",
            )
        )
    )


def sha256_file(path: Path, callback: Callable[[int], None] | None = None) -> str:
    try:
        before = path.lstat()
    except OSError as exc:
        raise BackupError(f"Impossibile ispezionare '{path}': {exc}") from exc
    if (
        _metadata_is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
    ):
        raise BackupError(f"File non sicuro (link/reparse/hardlink/tipo): '{path}'.")
    digest = hashlib.sha256()
    bytes_read = 0
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise BackupError(f"Impossibile aprire '{path}' per l'hash: {exc}") from exc
    try:
        opened = os.fstat(stream.fileno())
        if not _regular_hash_open_snapshot_is_valid(before, opened):
            raise BackupError(f"File sostituito durante l'apertura: '{path}'.")
        while chunk := stream.read(COPY_BUFFER_SIZE):
            digest.update(chunk)
            bytes_read += len(chunk)
            if callback:
                callback(len(chunk))
        opened_after = os.fstat(stream.fileno())
        try:
            current = path.lstat()
        except OSError as exc:
            raise BackupError(f"Il file è cambiato durante l'hash: '{path}': {exc}") from exc
        if not _regular_hash_final_snapshot_is_valid(
            before,
            opened,
            opened_after,
            current,
            bytes_read=bytes_read,
        ):
            raise BackupError(f"Il file è cambiato durante l'hash: '{path}'.")
    finally:
        stream.close()
    return digest.hexdigest()


def validate_game_archive_profile(
    game_dir: str | Path,
    profile: GameArchiveProfile,
) -> str:
    """Autentica rapidamente BHD e dimensioni dei BDT senza leggere i BDT da più GiB."""

    sd_dir = Path(game_dir).resolve() / "sd"
    if not sd_dir.is_dir():
        raise ArchiveProfileError("Cartella audio sd non trovata.")
    expected = {item.stem.casefold(): item for item in profile.archives}
    observed_bhds = {
        path.stem.casefold(): path
        for path in sd_dir.glob("sd*.bhd")
        if ARCHIVE_NAME_RE.fullmatch(path.name)
    }
    if set(observed_bhds) != set(expected):
        missing = sorted(set(expected).difference(observed_bhds))
        extra = sorted(set(observed_bhds).difference(expected))
        raise ArchiveProfileError(
            "Insieme di archivi audio fuori dal profilo omologato "
            f"(mancanti={missing}, in più={extra})."
        )
    for stem, fingerprint in expected.items():
        bhd_path = observed_bhds[stem]
        try:
            bhd_digest = sha256_file(bhd_path)
        except (BackupError, OSError) as exc:
            raise ArchiveProfileError(
                f"{bhd_path.name} non può essere autenticato in sicurezza: {exc}"
            ) from exc
        if bhd_digest != fingerprint.bhd_sha256:
            raise ArchiveProfileError(
                f"{bhd_path.name} non corrisponde al profilo {profile.profile_id}."
            )
        bdt_path = bhd_path.with_suffix(".bdt")
        try:
            metadata = bdt_path.lstat()
        except OSError as exc:
            raise ArchiveProfileError(
                f"Coppia BDT mancante o illeggibile per {bhd_path.name}."
            ) from exc
        if (
            _metadata_is_link_or_reparse(metadata)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
            or metadata.st_size != fingerprint.bdt_size
        ):
            raise ArchiveProfileError(
                f"{bdt_path.name} non è un file regolare esclusivo con la dimensione "
                f"del profilo {profile.profile_id}."
            )
    return profile.profile_id


def _copy_with_sha256(source: Path, destination: Path) -> str:
    digest = hashlib.sha256()
    with source.open("rb") as src, destination.open("xb") as dst:
        while chunk := src.read(COPY_BUFFER_SIZE):
            dst.write(chunk)
            digest.update(chunk)
        dst.flush()
        os.fsync(dst.fileno())
        opened = os.fstat(dst.fileno())
    current = destination.lstat()
    if (
        _metadata_is_link_or_reparse(current)
        or not stat.S_ISREG(opened.st_mode)
        or not stat.S_ISREG(current.st_mode)
        or opened.st_nlink != 1
        or current.st_nlink != 1
        or (opened.st_dev, opened.st_ino) != (current.st_dev, current.st_ino)
    ):
        raise BackupError(
            f"La copia temporanea è cambiata o possiede un hardlink: '{destination}'."
        )
    return digest.hexdigest()


def _regular_file_identity(path: Path, *, label: str) -> tuple[int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise BackupError(
            f"Impossibile ispezionare {label} '{path}': {exc}"
        ) from exc
    if (
        _metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise BackupError(f"{label} è cambiato o possiede un hardlink: '{path}'.")
    return metadata.st_dev, metadata.st_ino


def _open_owned_regular_for_update(
    path: Path, expected_identity: tuple[int, int], *, label: str
) -> BinaryIO:
    """Open an app-created file and prove no path swap happened before writes."""

    before = path.lstat()
    if (
        _metadata_is_link_or_reparse(before)
        or not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or (before.st_dev, before.st_ino) != expected_identity
    ):
        raise BackupError(f"{label} è cambiato prima dell'apertura: '{path}'.")
    try:
        stream = path.open("r+b", buffering=0)
    except OSError as exc:
        raise BackupError(f"Impossibile aprire {label} '{path}': {exc}") from exc
    try:
        opened = os.fstat(stream.fileno())
        current = path.lstat()
        if (
            _metadata_is_link_or_reparse(current)
            or not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or opened.st_nlink != 1
            or current.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != expected_identity
            or (current.st_dev, current.st_ino) != expected_identity
        ):
            raise BackupError(f"{label} è cambiato durante l'apertura: '{path}'.")
        return stream
    except Exception:
        stream.close()
        raise


def _sha256_owned_regular(path: Path, expected_identity: tuple[int, int]) -> str:
    """Hash one scratch file through a handle bound to its captured identity."""

    before = _regular_file_identity(path, label="Il file temporaneo")
    if before != expected_identity:
        raise BackupError(f"Il file temporaneo è stato sostituito: '{path}'.")
    try:
        before_metadata = path.lstat()
    except OSError as exc:
        raise BackupError(f"Il file temporaneo è cambiato: '{path}': {exc}") from exc
    digest = hashlib.sha256()
    bytes_read = 0
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise BackupError(
            f"Impossibile aprire il file temporaneo: {exc}"
        ) from exc
    try:
        opened = os.fstat(stream.fileno())
        if (
            (before_metadata.st_dev, before_metadata.st_ino) != expected_identity
            or not _regular_hash_open_snapshot_is_valid(before_metadata, opened)
        ):
            raise BackupError(f"Il file temporaneo è stato sostituito: '{path}'.")
        while chunk := stream.read(COPY_BUFFER_SIZE):
            digest.update(chunk)
            bytes_read += len(chunk)
        opened_after = os.fstat(stream.fileno())
        try:
            current = path.lstat()
        except OSError as exc:
            raise BackupError(
                f"Il file temporaneo è cambiato durante l'hash: '{path}': {exc}"
            ) from exc
        if not _regular_hash_final_snapshot_is_valid(
            before_metadata,
            opened,
            opened_after,
            current,
            bytes_read=bytes_read,
        ):
            raise BackupError(f"Il file temporaneo è cambiato durante l'hash: '{path}'.")
        return digest.hexdigest()
    finally:
        stream.close()


def _unlink_owned_regular(
    path: Path, expected_identity: tuple[int, int] | None
) -> bool:
    """Remove only the exact scratch inode/file-id created by this process."""

    if expected_identity is None:
        return False
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return True
    if (
        _metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != expected_identity
    ):
        return False
    path.unlink()
    return True


def _sha256_if_file(path: Path) -> str | None:
    """Return a digest for a regular file, or ``None`` when it is absent."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return None
    if (
        _metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise BackupError(f"File non sicuro (link/reparse/hardlink/tipo): '{path}'.")
    return sha256_file(path)


def _authenticated_regular_if_file(
    path: Path, *, label: str
) -> tuple[str | None, tuple[int, int] | None]:
    """Return digest and identity from the same regular, single-link inode."""

    try:
        path.lstat()
    except FileNotFoundError:
        return None, None
    identity = _regular_file_identity(path, label=label)
    return _sha256_owned_regular(path, identity), identity


def _publish_without_replace(source: Path, destination: Path) -> None:
    """Publish ``source`` atomically while refusing to clobber ``destination``.

    Both paths are deliberately created in the same game directory. Windows
    ``os.rename`` and Linux ``renameat2(RENAME_NOREPLACE)`` both perform one
    atomic move and refuse a destination created by another process.
    """
    if os.path.lexists(destination):
        raise BackupError(
            f"{destination.name} è ricomparso durante lo scambio; il file esterno è stato preservato."
        )
    try:
        _rename_noreplace(source, destination)
    except FileExistsError as exc:
        raise BackupError(
            f"{destination.name} è ricomparso durante lo scambio; il file esterno è stato preservato."
        ) from exc


def _publish_owned_without_replace(
    source: Path,
    destination: Path,
    expected_identity: tuple[int, int],
) -> None:
    """Publish only the exact private file created and authenticated by us."""

    if _regular_file_identity(source, label="La copia privata") != expected_identity:
        raise BackupError(f"La copia privata è stata sostituita: '{source}'.")
    _publish_without_replace(source, destination)
    try:
        if (
            _regular_file_identity(destination, label="La copia pubblicata")
            != expected_identity
        ):
            raise BackupError(f"La copia pubblicata è stata sostituita: '{destination}'.")
    except Exception:
        # Do not leave an unsafe entry live. Moving the just-published name back
        # makes the journal able to restore the authenticated rollback.
        if not os.path.lexists(source) and os.path.lexists(destination):
            try:
                _publish_without_replace(destination, source)
            except Exception:
                pass
        raise


def _rename_directory_without_replace(source: Path, destination: Path) -> None:
    """Publish a completed backup tree without replacing a racing directory."""

    if destination.exists() or destination.is_symlink():
        raise BackupError(
            f"La cartella {destination.name} è ricomparsa; il contenuto esterno è stato preservato."
        )
    try:
        _rename_noreplace(source, destination)
    except FileExistsError as exc:
        raise BackupError(
            f"La cartella {destination.name} è ricomparsa; il contenuto esterno è stato preservato."
        ) from exc
    except OSError as exc:
        raise BackupError(
            f"Impossibile pubblicare atomicamente il backup {destination.name}."
        ) from exc
    if source.exists() or not destination.is_dir():
        raise BackupError(
            f"La pubblicazione atomica del backup {destination.name} non è stata confermata."
        )


def _atomic_json(path: Path, value: dict) -> None:
    _ensure_safe_directory_tree(path.parent, label="La cartella del manifesto")
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    owned_identity: tuple[int, int] | None = None
    try:
        with temp_path.open("x", encoding="utf-8", newline="\n") as stream:
            opened = os.fstat(stream.fileno())
            owned_identity = (opened.st_dev, opened.st_ino)
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        metadata = temp_path.lstat()
        if (
            _metadata_is_link_or_reparse(metadata)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise BackupError(
                f"Il manifesto temporaneo è cambiato o possiede un hardlink: '{temp_path}'."
            )
        if (metadata.st_dev, metadata.st_ino) != owned_identity:
            raise BackupError(f"Il manifesto temporaneo è stato sostituito: '{temp_path}'.")
        os.replace(temp_path, path)
        _fsync_directory(path.parent)
    except FileExistsError as exc:
        raise BackupError(
            f"Lo scratch del manifesto esiste già ed è stato preservato: '{temp_path}'."
        ) from exc
    finally:
        try:
            _unlink_owned_regular(temp_path, owned_identity)
        except (OSError, BackupError):
            pass


def _default_backup_root() -> Path:
    if _is_windows():
        local_data = os.environ.get("LOCALAPPDATA")
        root = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
    else:
        configured = os.environ.get("XDG_STATE_HOME")
        candidate = Path(configured).expanduser() if configured else None
        root = (
            candidate
            if candidate is not None and candidate.is_absolute()
            else Path.home() / ".local" / "state"
        )
    return root / "ERITA" / "backups"


def _iter_backup_manifest_paths(backup_root: Path) -> tuple[Path, ...]:
    """Enumerate only regular manifests below validated app-owned directories."""

    if not backup_root.is_dir():
        return ()
    result: list[Path] = []
    for game_root in backup_root.iterdir():
        if not re.fullmatch(r"[0-9a-f]{16}", game_root.name):
            continue
        metadata = game_root.lstat()
        if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise BackupError(
                f"La cartella di backup possiede un tipo non sicuro ed è stata preservata: '{game_root}'."
            )
        for build_root in game_root.iterdir():
            if not re.fullmatch(r"[0-9a-f]{64}", build_root.name):
                continue
            metadata = build_root.lstat()
            if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
                metadata.st_mode
            ):
                raise BackupError(
                    "La cartella di fingerprint possiede un tipo non sicuro ed è stata preservata: "
                    f"'{build_root}'."
                )
            manifest = build_root / "manifest.json"
            if not os.path.lexists(manifest):
                continue
            metadata = manifest.lstat()
            if (
                _metadata_is_link_or_reparse(metadata)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise BackupError(
                    f"Manifesto di backup non sicuro e preservato: '{manifest}'."
                )
            result.append(manifest)
    return tuple(result)


class GameOperationLock:
    """Mutex su file tra processi per un'installazione del gioco."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = None

    def __enter__(self) -> "GameOperationLock":
        self._stream = _open_safe_operation_lock(self.path)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - la release attuale è Windows
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self._stream.close()
            self._stream = None
            raise PatcherError(
                "Un'altra istanza di ERITA sta già lavorando su questa installazione. "
                "Chiudi l'altra finestra e attendi il termine dell'operazione."
            ) from exc
        return self

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        if self._stream is None:
            return
        try:
            self._stream.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:  # pragma: no cover - la release attuale è Windows
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()
            self._stream = None


class BackupManager:
    """Backup completi, collegati al fingerprint esatto della build del gioco."""

    def __init__(
        self,
        game_dir: Path,
        archives: Sequence[Archive],
        backup_root: Path | None = None,
        log: Callable[[str], None] | None = None,
        precommit_guard: Callable[[], None] | None = None,
        expected_original_sha256: Mapping[str, str] | None = None,
    ) -> None:
        if not archives:
            raise BackupError("Nessun file BDT verrebbe modificato.")
        self.game_dir = game_dir.resolve()
        self.archives = tuple(
            sorted(archives, key=lambda item: item.bdt_path.name.lower())
        )
        self.backup_root = _ensure_safe_directory_tree(
            backup_root or _default_backup_root(), label="La radice dei backup"
        )
        self.log = log or (lambda _message: None)
        self.precommit_guard = precommit_guard or (lambda: None)
        self.expected_original_sha256 = {
            name.casefold(): digest
            for name, digest in (expected_original_sha256 or {}).items()
        }
        archive_names = {item.bdt_path.name.casefold() for item in self.archives}
        if self.expected_original_sha256 and (
            set(self.expected_original_sha256) != archive_names
            or any(
                not SHA256_RE.fullmatch(digest)
                for digest in self.expected_original_sha256.values()
            )
        ):
            raise ValueError(
                "Gli hash vanilla attesi non coprono esattamente gli archivi."
            )
        self.game_id = hashlib.sha256(
            _path_identity_text(self.game_dir).encode("utf-8")
        ).hexdigest()[:16]
        fingerprint_source = [
            {
                "bhd": item.bhd_path.name.lower(),
                "bhd_sha256": item.bhd_sha256,
                "bdt": item.bdt_path.name.lower(),
                "bdt_size": item.bdt_size,
            }
            for item in self.archives
        ]
        encoded = json.dumps(
            fingerprint_source, sort_keys=True, separators=(",", ":")
        ).encode()
        self.fingerprint = hashlib.sha256(encoded).hexdigest()
        self.directory = self.backup_root / self.game_id / self.fingerprint
        self.manifest_path = self.directory / "manifest.json"
        # One account-global lock also serializes a library while its Steam path
        # is being moved. Separate Windows accounts are documented as unsupported.
        self.lock_path = self.backup_root / ".operation.lock"

    def operation_lock(self) -> GameOperationLock:
        return GameOperationLock(self.lock_path)

    def _legacy_backups(self) -> list[Path]:
        return [
            archive.bdt_path.with_name(archive.bdt_path.name + ".original")
            for archive in self.archives
            if archive.bdt_path.with_name(archive.bdt_path.name + ".original").exists()
        ]

    def _manifest_template(self) -> dict:
        return {
            "schema": BACKUP_SCHEMA,
            "backup_id": str(uuid.uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "game_dir": str(self.game_dir),
            "game_id": self.game_id,
            "build_fingerprint": self.fingerprint,
            "state": "prepared",
            "archives": [],
        }

    def _load_manifest(self) -> dict:
        try:
            metadata = self.manifest_path.lstat()
            if (
                _metadata_is_link_or_reparse(metadata)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise BackupError(
                    f"Il manifesto di backup non è un file regolare esclusivo: "
                    f"{self.manifest_path}"
                )
            value = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except BackupError:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise BackupError(
                f"Manifesto di backup illeggibile: {self.manifest_path}"
            ) from exc
        if not isinstance(value, dict):
            raise BackupError(f"Manifesto di backup non valido: {self.manifest_path}")
        if value.get("schema") != BACKUP_SCHEMA:
            raise BackupError("Versione sconosciuta del manifesto di backup.")
        if value.get("build_fingerprint") != self.fingerprint:
            raise BackupError("Il backup appartiene a un'altra build del gioco.")
        if value.get("game_id") != self.game_id:
            raise BackupError("Il backup appartiene a un'altra installazione del gioco.")
        saved_game = value.get("game_dir")
        if (
            not isinstance(saved_game, str)
            or Path(saved_game).resolve() != self.game_dir
        ):
            raise BackupError("Il backup appartiene a un'altra installazione del gioco.")
        return value

    def _validate_backup(self, manifest: dict) -> None:
        records = manifest.get("archives")
        if not isinstance(records, list) or len(records) != len(self.archives):
            raise BackupError("Manifesto di backup incompleto.")
        expected_by_name = {item.bdt_path.name: item for item in self.archives}
        seen: set[str] = set()
        for record in records:
            if not isinstance(record, dict):
                raise BackupError("Voce non valida nel manifesto di backup.")
            name = record.get("bdt")
            archive = expected_by_name.get(name)
            if archive is None or name in seen:
                raise BackupError(f"File inaspettato nel backup: {name!r}.")
            seen.add(name)
            original_digest = record.get("sha256")
            patched_digest = record.get("patched_sha256")
            if (
                record.get("bhd") != archive.bhd_path.name
                or record.get("bhd_sha256") != archive.bhd_sha256
                or record.get("bdt_size") != archive.bdt_size
                or not isinstance(original_digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", original_digest)
                or (
                    patched_digest is not None
                    and (
                        not isinstance(patched_digest, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", patched_digest)
                    )
                )
            ):
                raise BackupError(f"Metadati non validi nel backup di {name}.")
            pinned_original = self.expected_original_sha256.get(name.casefold())
            if pinned_original is not None and original_digest != pinned_original:
                raise ArchiveProfileError(
                    f"Il backup originale di {name} non appartiene al profilo omologato."
                )
            backup_name = record.get("backup")
            if backup_name != f"{name}.backup":
                raise BackupError(f"Percorso di backup non valido per {name!r}.")
            backup_path = self.directory / backup_name
            try:
                metadata = backup_path.lstat()
            except FileNotFoundError as exc:
                raise BackupError(f"File di backup assente: {name}.") from exc
            if (
                backup_path.parent != self.directory
                or _metadata_is_link_or_reparse(metadata)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise BackupError(f"File di backup assente: {name}.")
            if metadata.st_size != archive.bdt_size:
                raise BackupError(f"Dimensione errata nel backup di {name}.")
            if sha256_file(backup_path) != original_digest:
                raise BackupError(f"SHA-256 errato nel backup di {name}.")
        if seen != set(expected_by_name):
            raise BackupError("Manifesto di backup incompleto.")
        valid_states = {
            "prepared",
            "applied",
            "restored",
            "applying",
            "staging",
            "preparing_commit",
            "committing",
            "restoring",
            "recovery_required",
        }
        state = manifest.get("state")
        if state not in valid_states:
            raise BackupError("Stato non valido nel manifesto di backup.")
        self._validate_transaction_journal(
            manifest,
            required=state
            in {
                "applying",
                "staging",
                "preparing_commit",
                "committing",
                "restoring",
                "recovery_required",
            },
        )

    def _validate_live_state(self, manifest: dict) -> dict[Path, str]:
        """Accetta solo l'originale salvato o l'ultimo risultato di ERITA.

        Questo impedisce di riutilizzare silenziosamente un backup se Steam sostituisce
        solo il contenuto del BDT, mantenendo lo stesso BHD e la stessa dimensione del file.
        """
        records = {record["bdt"]: record for record in manifest["archives"]}
        transaction = manifest.get("transaction") or {}
        transaction_pre = transaction.get("pre_sha256") or {}
        transaction_new = transaction.get("new_sha256") or {}
        result: dict[Path, str] = {}
        for archive in self.archives:
            if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                raise BackupError(f"{archive.bhd_path.name} è cambiato dal backup.")
            if (
                not archive.bdt_path.is_file()
                or archive.bdt_path.stat().st_size != archive.bdt_size
            ):
                raise BackupError(
                    f"{archive.bdt_path.name} ha cambiato dimensione dal backup."
                )
            record = records[archive.bdt_path.name]
            allowed = {record["sha256"]}
            if record.get("patched_sha256"):
                allowed.add(record["patched_sha256"])
            if transaction_pre.get(archive.bdt_path.name):
                allowed.add(transaction_pre[archive.bdt_path.name])
            if transaction_new.get(archive.bdt_path.name):
                allowed.add(transaction_new[archive.bdt_path.name])
            current = sha256_file(archive.bdt_path)
            if current not in allowed:
                raise BackupError(
                    f"{archive.bdt_path.name} è stato modificato al di fuori di questa installazione. "
                    "Usa 'Verifica integrità dei file' su Steam. Dopo aver confermato "
                    "l'audio originale, chiudi il patcher e sposta la cartella di backup di questa build "
                    f"in un'altra posizione prima di riprovare: {self.directory}"
                )
            result[archive.bdt_path] = current
        return result

    def _assert_live_snapshot(self, manifest: dict, expected: dict[Path, str]) -> None:
        current = self._validate_live_state(manifest)
        changed = [
            path.name
            for path, digest in expected.items()
            if current.get(path) != digest
        ]
        if changed:
            raise BackupError(
                "Lo stato del gioco è cambiato durante la preparazione dell'operazione "
                f"({', '.join(changed)}). Nessun file esterno è stato sovrascritto."
            )

    def _transaction_path(self, name: str) -> Path:
        if not isinstance(name, str) or not TRANSACTION_FILE_RE.fullmatch(name):
            raise BackupError("Percorso di recupero non valido nel manifesto.")
        path = self.archives[0].bdt_path.parent / name
        if path.parent != self.archives[0].bdt_path.parent:
            raise BackupError("Percorso di recupero non valido nel manifesto.")
        return path

    def _transaction_names(
        self,
        transaction: dict,
        archive: Archive,
    ) -> tuple[str, str]:
        transaction_id = transaction.get("id")
        if not isinstance(transaction_id, str) or not re.fullmatch(
            r"[0-9a-f]{32}", transaction_id
        ):
            raise BackupError("Journal di recupero con identificatore non valido.")
        name = archive.bdt_path.name
        rollback_name = (transaction.get("rollback_files") or {}).get(name)
        displaced_name = (transaction.get("displaced_files") or {}).get(name)
        expected_rollback = f".erita-{transaction_id}-{name}.rollback"
        expected_displaced = f".erita-{transaction_id}-{name}.displaced"
        if rollback_name != expected_rollback or displaced_name != expected_displaced:
            raise BackupError(f"Journal di recupero non valido per {name}.")
        # Apply the generic path validation as a second line of defence before
        # any unlink/replace operation derived from a persisted manifest.
        self._transaction_path(rollback_name)
        self._transaction_path(displaced_name)
        return rollback_name, displaced_name

    def _validate_transaction_journal(
        self, manifest: dict, *, required: bool = False
    ) -> dict | None:
        """Validate every persisted journal field before any recovery access."""

        transaction = manifest.get("transaction")
        if transaction is None:
            if required:
                raise BackupError(
                    "Transazione interrotta senza journal completo. "
                    "Usa la verifica di Steam."
                )
            return None
        if not isinstance(transaction, dict):
            raise BackupError(
                "Journal di recupero non valido. Usa la verifica di Steam."
            )

        transaction_id = transaction.get("id")
        if not isinstance(transaction_id, str) or not re.fullmatch(
            r"[0-9a-f]{32}", transaction_id
        ):
            raise BackupError("Journal di recupero con identificatore non valido.")
        if transaction.get("kind") not in {"apply", "restore"}:
            raise BackupError("Journal di recupero con operazione non valida.")
        if transaction.get("previous_state") not in {
            "prepared",
            "applied",
            "restored",
        }:
            raise BackupError("Journal di recupero con stato precedente non valido.")
        cleanup_only = transaction.get("cleanup_only")
        if cleanup_only is not None and cleanup_only is not True:
            raise BackupError("Journal di recupero con pulizia non valida.")

        mappings: dict[str, dict] = {}
        for field in (
            "pre_sha256",
            "new_sha256",
            "previous_patched_sha256",
            "rollback_files",
            "displaced_files",
        ):
            value = transaction.get(field)
            if not isinstance(value, dict):
                raise BackupError(f"Journal di recupero con mappa {field} non valida.")
            mappings[field] = value

        archive_names = {archive.bdt_path.name for archive in self.archives}
        pre_hashes = mappings["pre_sha256"]
        new_hashes = mappings["new_sha256"]
        previous_hashes = mappings["previous_patched_sha256"]
        for field, hashes, allow_none in (
            ("pre_sha256", pre_hashes, False),
            ("new_sha256", new_hashes, False),
            ("previous_patched_sha256", previous_hashes, True),
        ):
            for name, digest in hashes.items():
                if not isinstance(name, str) or name not in archive_names:
                    raise BackupError(
                        f"Journal di recupero fa riferimento a un file non valido in {field}."
                    )
                if allow_none and digest is None:
                    continue
                if not isinstance(digest, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", digest
                ):
                    raise BackupError(
                        f"Journal di recupero contiene un hash non valido in {field}."
                    )

        pre_names = set(pre_hashes)
        if not pre_names:
            raise BackupError("Journal di recupero senza file da recuperare.")
        if set(new_hashes) - pre_names:
            raise BackupError(
                "Journal di recupero contiene nuovi hash di file sconosciuti."
            )
        if set(previous_hashes) != archive_names:
            raise BackupError(
                "Journal di recupero senza lo stato precedente di tutti i file."
            )
        if (
            set(mappings["rollback_files"]) != pre_names
            or set(mappings["displaced_files"]) != pre_names
        ):
            raise BackupError(
                "Journal di recupero con elenco file incompleto."
            )

        archives_by_name = {archive.bdt_path.name: archive for archive in self.archives}
        for name in sorted(pre_names, key=str.casefold):
            self._transaction_names(transaction, archives_by_name[name])
        return transaction

    def _mark_recovery_required(self, manifest: dict, details: str) -> None:
        failed = copy.deepcopy(manifest)
        failed["state"] = "recovery_required"
        self.save_manifest(failed)
        raise BackupError(
            "Il ripristino ha rilevato una modifica esterna e ha preservato i file "
            f"({details}). Chiudi Steam e usa la verifica di integrità."
        )

    def _discard_known_transaction_file(
        self,
        path: Path,
        allowed_hashes: set[str],
    ) -> bool:
        try:
            metadata = path.lstat()
        except FileNotFoundError:
            return True
        if (
            _metadata_is_link_or_reparse(metadata)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            self.log(
                f"Attenzione: {path.name} ha un tipo non sicuro ed è stato preservato per l'analisi."
            )
            return False
        identity = (metadata.st_dev, metadata.st_ino)
        try:
            digest = _sha256_owned_regular(path, identity)
        except (OSError, BackupError) as exc:
            self.log(f"Attenzione: {path.name} è cambiato ed è stato preservato: {exc}")
            return False
        if digest not in allowed_hashes:
            self.log(
                f"Attenzione: {path.name} ha un contenuto inaspettato ed è stato preservato per l'analisi."
            )
            return False
        try:
            removed = _unlink_owned_regular(path, identity)
            if not removed:
                self.log(f"Attenzione: {path.name} è cambiato prima della pulizia ed è stato preservato.")
            return removed
        except (OSError, BackupError) as exc:
            self.log(f"Attenzione: pulizia rimandata per {path.name}: {exc}")
            return False

    def recover_pending(self, manifest: dict) -> dict:
        """Riporta uno scambio interrotto allo stato esatto precedente al commit."""
        state = manifest.get("state")
        if state not in {
            "staging",
            "preparing_commit",
            "committing",
            "restoring",
            "recovery_required",
        }:
            return manifest
        transaction = self._validate_transaction_journal(manifest, required=True)
        assert transaction is not None
        pre_hashes = transaction["pre_sha256"]
        new_hashes = transaction["new_sha256"]
        records = {record["bdt"]: record for record in manifest["archives"]}
        archives_by_name = {archive.bdt_path.name: archive for archive in self.archives}
        if not pre_hashes or set(pre_hashes) - set(archives_by_name):
            raise BackupError(
                "Journal di recupero fa riferimento a file sconosciuti."
            )
        transaction_archives = tuple(
            archives_by_name[name] for name in sorted(pre_hashes, key=str.casefold)
        )
        observed: dict[Path, dict[str, object]] = {}
        unsafe: list[str] = []
        for archive in transaction_archives:
            name = archive.bdt_path.name
            expected_pre = pre_hashes.get(name)
            if not expected_pre:
                raise BackupError("Journal di recupero senza hash precedente.")
            if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                unsafe.append(archive.bhd_path.name)
                continue
            rollback_name, displaced_name = self._transaction_names(
                transaction, archive
            )
            rollback_path = self._transaction_path(rollback_name)
            displaced_path = self._transaction_path(displaced_name)
            current, current_identity = _authenticated_regular_if_file(
                archive.bdt_path, label="Il BDT attivo"
            )
            rollback, rollback_identity = _authenticated_regular_if_file(
                rollback_path, label="Il rollback del journal"
            )
            displaced, displaced_identity = _authenticated_regular_if_file(
                displaced_path, label="Il BDT spostato del journal"
            )
            observed[archive.bdt_path] = {
                "archive": archive,
                "pre": expected_pre,
                "new": new_hashes.get(name),
                "original": records[name]["sha256"],
                "current": current,
                "current_identity": current_identity,
                "rollback": rollback,
                "rollback_identity": rollback_identity,
                "rollback_path": rollback_path,
                "displaced": displaced,
                "displaced_identity": displaced_identity,
                "displaced_path": displaced_path,
            }

        # Steam Verify is the documented escape hatch after an external change.
        # When every live BDT is now the exact original held by this backup, clear
        # the stale journal instead of trapping the user in recovery_required.
        all_original = not unsafe
        if all_original:
            for archive in self.archives:
                record = records[archive.bdt_path.name]
                if (
                    sha256_file(archive.bhd_path) != archive.bhd_sha256
                    or _sha256_if_file(archive.bdt_path) != record["sha256"]
                ):
                    all_original = False
                    break
        if not unsafe and all_original:
            recovered = copy.deepcopy(manifest)
            for record in recovered["archives"]:
                record.pop("patched_sha256", None)
            cleanup_transaction = copy.deepcopy(transaction)
            cleanup_transaction["cleanup_only"] = True
            recovered["transaction"] = cleanup_transaction
            recovered["state"] = "restored"
            recovered["updated_at"] = datetime.now(timezone.utc).isoformat()
            _atomic_json(self.manifest_path, recovered)
            recovered = self._cleanup_completed_transaction(recovered)
            if recovered.get("transaction"):
                self.log(
                    "Steam Verify confermato; la pulizia del journal verrà ritentata."
                )
            else:
                self.log(
                    "Steam Verify confermato; il journal interrotto è stato chiuso."
                )
            return recovered

        for live_path, item in observed.items():
            current = item["current"]
            expected_pre = item["pre"]
            expected_new = item["new"]
            rollback = item["rollback"]
            displaced = item["displaced"]
            if current == expected_pre:
                if rollback not in {None, expected_pre} or displaced not in {
                    None,
                    expected_new,
                }:
                    unsafe.append(live_path.name)
                continue
            if (
                current == expected_new
                and rollback == expected_pre
                and displaced is None
            ):
                continue
            if (
                current is None
                and rollback == expected_pre
                and displaced in {None, expected_new}
            ):
                continue
            # If a prior recovery was interrupted just after moving an unknown
            # live file aside, put that exact file back before reporting the stop.
            if current is None and displaced not in {None, expected_new}:
                try:
                    displaced_identity = item["displaced_identity"]
                    if not isinstance(displaced_identity, tuple):
                        raise BackupError("Identità del BDT spostato assente.")
                    _publish_owned_without_replace(
                        item["displaced_path"], live_path, displaced_identity
                    )
                except Exception:
                    pass
            unsafe.append(live_path.name)

        if unsafe:
            self._mark_recovery_required(manifest, ", ".join(sorted(set(unsafe))))

        try:
            for live_path, item in observed.items():
                current, current_identity = _authenticated_regular_if_file(
                    live_path, label="Il BDT attivo"
                )
                expected_pre = item["pre"]
                expected_new = item["new"]
                rollback_path = item["rollback_path"]
                displaced_path = item["displaced_path"]
                if current == expected_pre:
                    continue
                if current == expected_new:
                    if os.path.lexists(displaced_path):
                        self._mark_recovery_required(manifest, live_path.name)
                    if not isinstance(current_identity, tuple):
                        self._mark_recovery_required(manifest, live_path.name)
                    _publish_owned_without_replace(
                        live_path, displaced_path, current_identity
                    )
                    if (
                        _sha256_owned_regular(displaced_path, current_identity)
                        != expected_new
                    ):
                        try:
                            _publish_owned_without_replace(
                                displaced_path, live_path, current_identity
                            )
                        finally:
                            self._mark_recovery_required(manifest, live_path.name)
                elif current is not None:
                    self._mark_recovery_required(manifest, live_path.name)
                # This is create-if-absent, so a Steam file that appears after
                # the checks above cannot be silently overwritten.
                rollback_identity = item["rollback_identity"]
                if not isinstance(rollback_identity, tuple) or (
                    _sha256_owned_regular(rollback_path, rollback_identity)
                    != expected_pre
                ):
                    self._mark_recovery_required(manifest, live_path.name)
                _publish_owned_without_replace(
                    rollback_path, live_path, rollback_identity
                )
                if _sha256_owned_regular(live_path, rollback_identity) != expected_pre:
                    try:
                        _publish_owned_without_replace(
                            live_path, rollback_path, rollback_identity
                        )
                    finally:
                        self._mark_recovery_required(manifest, live_path.name)
        except BackupError:
            raise
        except Exception as exc:
            self._mark_recovery_required(manifest, str(exc))

        final_unsafe: list[str] = []
        for live_path, item in observed.items():
            if _sha256_if_file(live_path) != item["pre"]:
                final_unsafe.append(live_path.name)
            archive = item["archive"]
            if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                final_unsafe.append(archive.bhd_path.name)
        if final_unsafe:
            self._mark_recovery_required(manifest, ", ".join(sorted(set(final_unsafe))))

        recovered = copy.deepcopy(manifest)
        previous_patched = transaction.get("previous_patched_sha256") or {}
        for record in recovered["archives"]:
            prior = previous_patched.get(record["bdt"])
            if prior:
                record["patched_sha256"] = prior
            else:
                record.pop("patched_sha256", None)
        cleanup_transaction = copy.deepcopy(transaction)
        cleanup_transaction["cleanup_only"] = True
        recovered["transaction"] = cleanup_transaction
        previous_state = transaction.get("previous_state", "prepared")
        recovered["state"] = (
            previous_state
            if previous_state in {"prepared", "applied", "restored"}
            else "prepared"
        )
        recovered["updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(self.manifest_path, recovered)
        recovered = self._cleanup_completed_transaction(recovered)
        if recovered.get("transaction"):
            self.log(
                "Stato precedente ripristinato; la pulizia del journal verrà ritentata."
            )
        else:
            self.log("Transazione interrotta ripristinata allo stato precedente.")
        return recovered

    def assert_no_foreign_pending(self) -> None:
        game_root = self.backup_root / self.game_id
        if not game_root.is_dir():
            return
        pending_states = {
            "applying",
            "staging",
            "preparing_commit",
            "committing",
            "restoring",
            "recovery_required",
        }
        for path in game_root.glob("*/manifest.json"):
            if path == self.manifest_path:
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(value, dict):
                raise BackupError(f"Manifesto precedente non valido: {path}.")
            transaction = value.get("transaction")
            completed_cleanup = isinstance(transaction, dict) and (
                transaction.get("cleanup_only") is True
                or value.get("state") in {"applied", "restored"}
            )
            if completed_cleanup:
                if self._cleanup_foreign_completed_transaction(path, value):
                    continue
            if value.get("state") in pending_states or isinstance(transaction, dict):
                journal_names: set[str] = set()
                if isinstance(transaction, dict):
                    for field in ("rollback_files", "displaced_files"):
                        mapping = transaction.get(field)
                        if isinstance(mapping, dict):
                            journal_names.update(
                                name
                                for name in mapping.values()
                                if isinstance(name, str)
                                and TRANSACTION_FILE_RE.fullmatch(name)
                            )
                journal_note = ""
                if journal_names:
                    sd_dir = self.archives[0].bdt_path.parent
                    exact_paths = ", ".join(
                        f"'{sd_dir / name}'" for name in sorted(journal_names)
                    )
                    journal_note = (
                        " Preserva anche, spostandoli nella stessa quarantena fuori da "
                        f"Game\\sd, i file di journal eventualmente presenti: {exact_paths}."
                    )
                raise BackupError(
                    "Esiste una transazione interrotta di un'altra build di questo gioco. "
                    "Chiudi Steam, usa 'Verifica integrità dei file' e conferma "
                    "che l'audio originale sia tornato. Poi sposta, senza eliminarla, la cartella esatta "
                    f"'{path.parent}' fuori da '{self.backup_root}' e riprova. "
                    "Il patcher non ritira mai automaticamente un journal di un'altra build."
                    + journal_note
                )

    def _cleanup_foreign_completed_transaction(
        self, manifest_path: Path, manifest: dict
    ) -> bool:
        """Pulisce nomi privati autenticati di un fingerprint precedente.

        Un aggiornamento di Steam può cambiare il fingerprint dopo che il ripristino
        ha lasciato in sospeso solo l'eliminazione di ``rollback``/``displaced``. Il journal
        precedente resta l'unica autorità in grado di riconoscere questi file.
        """

        transaction = manifest.get("transaction")
        is_completed_cleanup = isinstance(transaction, dict) and (
            transaction.get("cleanup_only") is True
            or manifest.get("state") in {"applied", "restored"}
        )
        saved_game = manifest.get("game_dir")
        if (
            manifest.get("schema") != BACKUP_SCHEMA
            or manifest.get("game_id") != self.game_id
            or not isinstance(saved_game, str)
            or Path(saved_game).resolve() != self.game_dir
            or not is_completed_cleanup
            or manifest.get("state") not in {"prepared", "applied", "restored"}
        ):
            return False
        fingerprint = manifest.get("build_fingerprint")
        if (
            not isinstance(fingerprint, str)
            or not re.fullmatch(r"[0-9a-f]{64}", fingerprint)
            or manifest_path.parent.name != fingerprint
            or manifest_path.name != "manifest.json"
        ):
            return False
        transaction_id = transaction.get("id")
        pre_hashes = transaction.get("pre_sha256")
        new_hashes = transaction.get("new_sha256") or {}
        rollback_files = transaction.get("rollback_files")
        displaced_files = transaction.get("displaced_files")
        records = manifest.get("archives")
        if (
            not isinstance(transaction_id, str)
            or not re.fullmatch(r"[0-9a-f]{32}", transaction_id)
            or not isinstance(pre_hashes, dict)
            or not pre_hashes
            or not isinstance(new_hashes, dict)
            or not isinstance(rollback_files, dict)
            or not isinstance(displaced_files, dict)
            or not isinstance(records, list)
        ):
            return False
        pre_names = set(pre_hashes)
        if (
            set(new_hashes) - pre_names
            or set(rollback_files) != pre_names
            or set(displaced_files) != pre_names
        ):
            # Never drop the only cleanup authority for an unrecognised journal
            # member in a manifest from an older build.
            return False
        originals = {
            record.get("bdt"): record.get("sha256")
            for record in records
            if isinstance(record, dict)
        }
        cleanup_complete = True
        for name, pre_digest in pre_hashes.items():
            if not isinstance(name, str) or not BDT_NAME_RE.fullmatch(name):
                return False
            expected_rollback = f".erita-{transaction_id}-{name}.rollback"
            expected_displaced = f".erita-{transaction_id}-{name}.displaced"
            if (
                rollback_files.get(name) != expected_rollback
                or displaced_files.get(name) != expected_displaced
                or not TRANSACTION_FILE_RE.fullmatch(expected_rollback)
                or not TRANSACTION_FILE_RE.fullmatch(expected_displaced)
            ):
                return False
            known = {
                value
                for value in (pre_digest, new_hashes.get(name), originals.get(name))
                if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
            }
            if pre_digest not in known or originals.get(name) not in known:
                return False
            cleanup_complete &= self._discard_known_transaction_file(
                self._transaction_path(expected_rollback), known
            )
            cleanup_complete &= self._discard_known_transaction_file(
                self._transaction_path(expected_displaced), known
            )
        if not cleanup_complete:
            return False
        cleaned = copy.deepcopy(manifest)
        cleaned.pop("transaction", None)
        _atomic_json(manifest_path, cleaned)
        self.log(
            f"Pulizia autenticata completata per il backup precedente {fingerprint[:12]}."
        )
        return True

    def assert_safe_new_baseline(self) -> None:
        """Never bless bytes patched by an older archive set as originals."""
        current_hashes: dict[str, str] = {}
        for path in _iter_backup_manifest_paths(self.backup_root):
            if path == self.manifest_path:
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("manifest")
                saved_game = value.get("game_dir")
                saved_game_id = value.get("game_id")
                saved_fingerprint = value.get("build_fingerprint")
                if not isinstance(saved_game, str):
                    raise ValueError("game path")
                saved_game_path = Path(saved_game).resolve()
                calculated_game_id = hashlib.sha256(
                    _path_identity_text(saved_game_path).encode("utf-8")
                ).hexdigest()[:16]
                if (
                    value.get("schema") != BACKUP_SCHEMA
                    or saved_game_id != calculated_game_id
                    or path.parent.parent.name != calculated_game_id
                    or not isinstance(saved_fingerprint, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", saved_fingerprint)
                    or path.parent.name != saved_fingerprint
                    or path.parent.parent.parent != self.backup_root
                ):
                    raise ValueError("manifest identity")
                records = value.get("archives")
                if not isinstance(records, list) or not records:
                    raise ValueError("archives")
                seen_records: set[str] = set()
                fingerprint_source: list[dict[str, str | int]] = []
                for record in records:
                    if not isinstance(record, dict):
                        raise ValueError("archive record")
                    bdt_name = record.get("bdt")
                    bhd_name = record.get("bhd")
                    bhd_digest = record.get("bhd_sha256")
                    bdt_size = record.get("bdt_size")
                    original_digest = record.get("sha256")
                    patched_digest = record.get("patched_sha256")
                    if (
                        not isinstance(bdt_name, str)
                        or not BDT_NAME_RE.fullmatch(bdt_name)
                        or bdt_name.casefold() in seen_records
                        or not isinstance(bhd_name, str)
                        or not ARCHIVE_NAME_RE.fullmatch(bhd_name)
                        or Path(bdt_name).with_suffix(".bhd").name.casefold()
                        != bhd_name.casefold()
                        or not isinstance(bhd_digest, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", bhd_digest)
                        or isinstance(bdt_size, bool)
                        or not isinstance(bdt_size, int)
                        or bdt_size < 0
                        or not isinstance(original_digest, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", original_digest)
                        or (
                            patched_digest is not None
                            and (
                                not isinstance(patched_digest, str)
                                or not re.fullmatch(r"[0-9a-f]{64}", patched_digest)
                            )
                        )
                    ):
                        raise ValueError("archive record")
                    seen_records.add(bdt_name.casefold())
                    fingerprint_source.append(
                        {
                            "bhd": bhd_name.lower(),
                            "bhd_sha256": bhd_digest,
                            "bdt": bdt_name.lower(),
                            "bdt_size": bdt_size,
                        }
                    )
                fingerprint_source.sort(key=lambda item: str(item["bdt"]).casefold())
                encoded = json.dumps(
                    fingerprint_source, sort_keys=True, separators=(",", ":")
                ).encode()
                if hashlib.sha256(encoded).hexdigest() != saved_fingerprint:
                    raise ValueError("build fingerprint")
            except (OSError, json.JSONDecodeError, ValueError) as exc:
                raise BackupError(
                    "Esiste un manifesto precedente illeggibile. Per non trasformare "
                    "un'installazione già modificata in un nuovo 'originale', usa la verifica "
                    "di integrità di Steam, conferma l'audio originale e sposta la "
                    f"cartella esatta in un'altra posizione senza eliminarla: {path.parent}"
                ) from exc
            originals = {
                record["bdt"].casefold(): record["sha256"] for record in records
            }
            records_by_name = {record["bdt"].casefold(): record for record in records}
            same_installation = (
                saved_game_id == self.game_id and saved_game_path == self.game_dir
            )
            for archive in self.archives:
                expected_original = originals.get(archive.bdt_path.name.casefold())
                if expected_original is None:
                    continue
                record = records_by_name[archive.bdt_path.name.casefold()]
                # For another saved Steam path, compare only the exact same BHD
                # layout. This catches a library moved while patched without
                # conflating an unrelated installation or older game build.
                if not same_installation and (
                    record["bhd_sha256"] != archive.bhd_sha256
                    or record["bdt_size"] != archive.bdt_size
                ):
                    continue
                if not isinstance(expected_original, str) or not re.fullmatch(
                    r"[0-9a-f]{64}", expected_original
                ):
                    raise BackupError(f"Manifesto precedente non valido: {path}.")
                current = current_hashes.get(archive.bdt_path.name)
                if current is None:
                    current = sha256_file(archive.bdt_path)
                    current_hashes[archive.bdt_path.name] = current
                if current != expected_original:
                    location_note = (
                        " di questa installazione"
                        if same_installation
                        else f" di un'altra posizione registrata ({saved_game_path})"
                    )
                    raise BackupError(
                        f"{archive.bdt_path.name} differisce ancora dall'originale salvato da "
                        f"un'installazione precedente{location_note}. Ripristina prima di spostare la "
                        "libreria; se è già stata spostata, usa la verifica di Steam, "
                        "conferma l'audio originale e "
                        f"sposta il vecchio backup in un'altra posizione prima di riprovare: {path.parent}"
                    )

    def cleanup_orphan_stages(self) -> None:
        sd_dir = self.archives[0].bdt_path.parent
        for archive in self.archives:
            patterns = (
                f".{archive.bdt_path.name}.erita-stage-*.tmp",
                f".{archive.bdt_path.name}.erita-restore-*.tmp",
            )
            for pattern in patterns:
                for candidate in sd_dir.glob(pattern):
                    # These transaction UUID names do not collide with the next
                    # attempt. Preserve them: deleting by pathname after a crash
                    # could race with an external rename into the same name.
                    self.log(
                        "Attenzione: copia transazionale interrotta preservata per "
                        f"pulizia manuale sicura: {candidate}"
                    )

    def cleanup_orphan_backup_staging(self) -> None:
        """Report private temp directories left by a killed baseline copy.

        Even a narrowly named directory can be exchanged for a junction after
        it has been inspected.  Walking it and unlinking children by pathname
        would therefore let a local race redirect cleanup outside our backup
        root.  Baseline copies are intentionally fail-safe: preserve every
        residue and tell the user its exact location instead of deleting it.
        """
        parent = self.directory.parent
        if not parent.is_dir():
            return
        # ``mkdtemp`` names are private implementation details inside this
        # game's app-owned backup directory.  Scan every build prefix: Steam
        # may have changed the BHD/BDT fingerprint after a killed copy, in
        # which case limiting cleanup to the current fingerprint leaks the
        # old multi-GiB staging directory forever.
        # Python 3.13's tempfile candidate is exactly eight characters from
        # ``abcdefghijklmnopqrstuvwxyz0123456789_``. Keep the destructive match
        # narrower than the broader set accepted by a generic safe filename.
        expected = re.compile(r"^\.[0-9a-f]{12}-[a-z0-9_]{8}$")
        for candidate in parent.iterdir():
            if candidate.parent != parent or not expected.fullmatch(candidate.name):
                continue
            try:
                candidate_metadata = candidate.lstat()
                if _metadata_is_link_or_reparse(candidate_metadata) or not stat.S_ISDIR(
                    candidate_metadata.st_mode
                ):
                    self.log(
                        f"Attenzione: staging di backup con tipo non sicuro preservato: {candidate}"
                    )
                    continue
                self.log(
                    "Attenzione: staging di backup incompleto preservato per pulizia "
                    f"manuale sicura: {candidate}"
                )
            except OSError as exc:
                self.log(f"Attenzione: vecchio staging di backup preservato: {exc}")

    def _cleanup_completed_transaction(self, manifest: dict) -> dict:
        transaction = manifest.get("transaction")
        if not isinstance(transaction, dict):
            return manifest
        cleanup_state = manifest.get("state") in {"applied", "restored"}
        if transaction.get("cleanup_only") is True:
            cleanup_state = manifest.get("state") in {
                "prepared",
                "applied",
                "restored",
            }
        if not cleanup_state:
            return manifest
        records = {record["bdt"]: record for record in manifest["archives"]}
        archives_by_name = {archive.bdt_path.name: archive for archive in self.archives}
        transaction_names = set((transaction.get("pre_sha256") or {}).keys())
        if not transaction_names or transaction_names - set(archives_by_name):
            raise BackupError("Journal concluso fa riferimento a file sconosciuti.")
        cleanup_complete = True
        for archive in (
            archives_by_name[name]
            for name in sorted(transaction_names, key=str.casefold)
        ):
            rollback_name, displaced_name = self._transaction_names(
                transaction, archive
            )
            known = {
                value
                for value in (
                    (transaction.get("pre_sha256") or {}).get(archive.bdt_path.name),
                    (transaction.get("new_sha256") or {}).get(archive.bdt_path.name),
                    records[archive.bdt_path.name]["sha256"],
                )
                if value
            }
            cleanup_complete &= self._discard_known_transaction_file(
                self._transaction_path(rollback_name), known
            )
            cleanup_complete &= self._discard_known_transaction_file(
                self._transaction_path(displaced_name), known
            )
        if not cleanup_complete:
            return manifest
        cleaned = copy.deepcopy(manifest)
        cleaned.pop("transaction", None)
        _atomic_json(self.manifest_path, cleaned)
        return cleaned

    def prepare(
        self,
        new_baseline_guard: Callable[[], object] | None = None,
    ) -> tuple[dict, bool, dict[Path, str]]:
        legacy = self._legacy_backups()
        if legacy:
            names = ", ".join(path.name for path in legacy)
            raise LegacyBackupError(
                "È stato trovato un backup del vecchio installatore "
                f"({names}). Usa 'Verifica integrità dei file' su Steam, "
                "conferma che il gioco sia tornato all'audio originale e rimuovi questo file "
                ".original prima di continuare. Non può essere ripristinato in sicurezza "
                "dopo un aggiornamento del gioco."
            )

        self.assert_no_foreign_pending()
        self.cleanup_orphan_stages()
        self.cleanup_orphan_backup_staging()
        if self.manifest_path.exists():
            manifest = self._load_manifest()
            self.log("Validazione del backup esistente (SHA-256) in corso...")
            self._validate_backup(manifest)
            manifest = self.recover_pending(manifest)
            live_hashes = self._validate_live_state(manifest)
            manifest = self._cleanup_completed_transaction(manifest)
            if manifest.get("transaction"):
                raise BackupError(
                    "C'è ancora una pulizia di una transazione precedente in sospeso. "
                    "Chiudi Steam, esegui di nuovo e non aprire il gioco finché la verifica non è completata."
                )
            return manifest, False, live_hashes

        self.assert_safe_new_baseline()
        _ensure_safe_directory_tree(self.backup_root, label="La radice dei backup")
        needed = sum(item.bdt_size for item in self.archives) + 64 * 1024 * 1024
        free = shutil.disk_usage(self.backup_root).free
        if free < needed:
            raise BackupError(
                "Spazio insufficiente per il backup sicuro: "
                f"necessario {needed / (1024**3):.2f} GiB; "
                f"disponibile {free / (1024**3):.2f} GiB."
            )

        # Bind the baseline to the exact bytes observed before the first copy.
        # Size/mtime alone cannot detect a same-size replacement made while a
        # multi-GiB backup is being produced.
        baseline_hashes: dict[Path, str] = {}
        for archive in self.archives:
            if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                raise BackupError(
                    f"{archive.bhd_path.name} è cambiato prima della creazione del backup."
                )
            before = archive.bdt_path.stat()
            if (
                before.st_size != archive.bdt_size
                or before.st_mtime_ns != archive.bdt_mtime_ns
            ):
                raise BackupError(
                    f"{archive.bdt_path.name} è cambiato prima della creazione del backup."
                )
            self.log(f"Autenticazione dello stato iniziale di {archive.bdt_path.name} in corso...")
            digest = sha256_file(archive.bdt_path)
            after = archive.bdt_path.stat()
            if (
                after.st_size != before.st_size
                or after.st_mtime_ns != before.st_mtime_ns
                or sha256_file(archive.bhd_path) != archive.bhd_sha256
            ):
                raise BackupError(
                    f"{archive.bdt_path.name} è cambiato durante l'autenticazione iniziale."
                )
            pinned_original = self.expected_original_sha256.get(
                archive.bdt_path.name.casefold()
            )
            if pinned_original is not None and digest != pinned_original:
                raise ArchiveProfileError(
                    f"{archive.bdt_path.name} non corrisponde al baseline vanilla "
                    "del profilo omologato. Nessun file del gioco è stato modificato."
                )
            baseline_hashes[archive.bdt_path] = digest

        # Fix the full-file hashes first, then authenticate the exact live BHD
        # ranges before any backup directory is created.  The copies below must
        # still match these already-fixed hashes, closing the gap between the
        # salted guard and publication of a new immutable baseline.
        if new_baseline_guard is not None:
            new_baseline_guard()

        parent = self.directory.parent
        parent.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(
            tempfile.mkdtemp(prefix=f".{self.fingerprint[:12]}-", dir=parent)
        )
        manifest = self._manifest_template()
        try:
            for archive in self.archives:
                backup_name = archive.bdt_path.name + ".backup"
                self.log(f"Creazione del backup di {archive.bdt_path.name} in corso...")
                digest = _copy_with_sha256(archive.bdt_path, temp_dir / backup_name)
                if digest != baseline_hashes[archive.bdt_path]:
                    raise BackupError(
                        f"{archive.bdt_path.name} è cambiato durante la copia del backup. "
                        "Il baseline non è stato creato."
                    )
                manifest["archives"].append(
                    {
                        "bhd": archive.bhd_path.name,
                        "bhd_sha256": archive.bhd_sha256,
                        "bdt": archive.bdt_path.name,
                        "bdt_size": archive.bdt_size,
                        "backup": backup_name,
                        "sha256": baseline_hashes[archive.bdt_path],
                    }
                )
            for archive in self.archives:
                if (
                    sha256_file(archive.bhd_path) != archive.bhd_sha256
                    or archive.bdt_path.stat().st_size != archive.bdt_size
                    or sha256_file(archive.bdt_path)
                    != baseline_hashes[archive.bdt_path]
                ):
                    raise BackupError(
                        f"{archive.bdt_path.name} è cambiato prima della pubblicazione del backup. "
                        "Il baseline non è stato creato."
                    )
            _atomic_json(temp_dir / "manifest.json", manifest)
            _rename_directory_without_replace(temp_dir, self.directory)
        except Exception:
            # Recursive deletion by pathname can be redirected if a same-user
            # process swaps this long-lived directory while the multi-GiB copy
            # is running. Preserve the residue and expose the exact path for a
            # deliberate manual cleanup after the failure is understood.
            self.log(
                "Attenzione: staging di backup incompleto preservato per pulizia "
                f"manuale sicura: {temp_dir}"
            )
            raise
        self._validate_backup(manifest)
        live_hashes = self._validate_live_state(manifest)
        return manifest, True, live_hashes

    def set_state(self, manifest: dict, state: str) -> None:
        manifest = dict(manifest)
        manifest["state"] = state
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(self.manifest_path, manifest)

    def save_manifest(self, manifest: dict) -> None:
        value = copy.deepcopy(manifest)
        value["updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(self.manifest_path, value)

    def restore(self, manifest: dict | None = None) -> None:
        manifest = manifest or self._load_manifest()
        self._validate_backup(manifest)
        manifest = self.recover_pending(manifest)
        self.cleanup_orphan_stages()
        self.cleanup_orphan_backup_staging()
        manifest = self._cleanup_completed_transaction(manifest)
        live_snapshot = self._validate_live_state(manifest)
        records = {record["bdt"]: record for record in manifest["archives"]}

        if manifest.get("state") == "restored" and all(
            live_snapshot[archive.bdt_path] == records[archive.bdt_path.name]["sha256"]
            for archive in self.archives
        ):
            self.log("I file originali sono già stati ripristinati.")
            return
        if manifest.get("transaction"):
            raise BackupError(
                "C'è ancora una pulizia di una transazione precedente in sospeso. "
                "Chiudi Steam e prova a ripristinare di nuovo."
            )

        needed = sum(item.bdt_size for item in self.archives) + 64 * 1024 * 1024
        free = shutil.disk_usage(self.archives[0].bdt_path.parent).free
        if free < needed:
            raise BackupError(
                "Spazio insufficiente per preparare il ripristino atomico: "
                f"necessario {needed / (1024**3):.2f} GiB; "
                f"disponibile {free / (1024**3):.2f} GiB."
            )

        transaction_id = uuid.uuid4().hex
        transaction = {
            "id": transaction_id,
            "kind": "restore",
            "previous_state": manifest.get("state", "applied"),
            "pre_sha256": {
                archive.bdt_path.name: live_snapshot[archive.bdt_path]
                for archive in self.archives
            },
            "previous_patched_sha256": {
                record["bdt"]: record.get("patched_sha256")
                for record in manifest["archives"]
            },
            "new_sha256": {
                record["bdt"]: record["sha256"] for record in manifest["archives"]
            },
            "rollback_files": {
                archive.bdt_path.name: (
                    f".erita-{transaction_id}-{archive.bdt_path.name}.rollback"
                )
                for archive in self.archives
            },
            "displaced_files": {
                archive.bdt_path.name: (
                    f".erita-{transaction_id}-{archive.bdt_path.name}.displaced"
                )
                for archive in self.archives
            },
        }
        staged: dict[Path, Path] = {}
        staged_identities: dict[Path, tuple[int, int]] = {}
        transaction_saved = False
        try:
            for archive in self.archives:
                record = records[archive.bdt_path.name]
                source = self.directory / record["backup"]
                temp = archive.bdt_path.with_name(
                    f".{archive.bdt_path.name}.erita-restore-{transaction_id}.tmp"
                )
                if temp.exists():
                    raise BackupError(f"File temporaneo inaspettato: {temp.name}.")
                self.log(f"Preparazione del ripristino di {archive.bdt_path.name} in corso...")
                digest = _copy_with_sha256(source, temp)
                if digest != record["sha256"]:
                    raise BackupError(
                        f"Errore nella copia del backup di {archive.bdt_path.name}."
                    )
                staged[archive.bdt_path] = temp
                staged_identities[archive.bdt_path] = _regular_file_identity(
                    temp, label="La copia temporanea di ripristino"
                )

            for archive in self.archives:
                record = records[archive.bdt_path.name]
                if (
                    _sha256_owned_regular(
                        staged[archive.bdt_path],
                        staged_identities[archive.bdt_path],
                    )
                    != record["sha256"]
                ):
                    raise BackupError(
                        f"La copia di ripristino è cambiata per {archive.bdt_path.name}."
                    )

            # The full copies above can take minutes.  Re-hash every live BDT now,
            # immediately before journalling and swapping anything.
            self._assert_live_snapshot(manifest, live_snapshot)
            self.precommit_guard()
            working = copy.deepcopy(manifest)
            working["transaction"] = transaction
            working["state"] = "restoring"
            self.save_manifest(working)
            transaction_saved = True

            for archive in self.archives:
                rollback_name, displaced_name = self._transaction_names(
                    transaction, archive
                )
                rollback_path = self._transaction_path(rollback_name)
                displaced_path = self._transaction_path(displaced_name)
                if rollback_path.exists() or displaced_path.exists():
                    raise BackupError(
                        f"File di transazione inaspettato per {archive.bdt_path.name}."
                    )
                if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                    raise BackupError(
                        f"{archive.bhd_path.name} è cambiato durante il ripristino."
                    )
                if (
                    _regular_file_identity(
                        staged[archive.bdt_path],
                        label="La copia temporanea di ripristino",
                    )
                    != staged_identities[archive.bdt_path]
                ):
                    raise BackupError(
                        f"La copia di ripristino è stata sostituita per {archive.bdt_path.name}."
                    )

                # Move first, then hash the moved inode.  If Steam replaces the
                # live path after the earlier check, its bytes are retained here
                # and are put back instead of being overwritten.
                _publish_without_replace(archive.bdt_path, rollback_path)
                if sha256_file(rollback_path) != live_snapshot[archive.bdt_path]:
                    try:
                        _publish_without_replace(rollback_path, archive.bdt_path)
                    finally:
                        raise BackupError(
                            f"{archive.bdt_path.name} è cambiato nell'istante dello scambio; "
                            "il file trovato è stato preservato."
                        )
                _publish_owned_without_replace(
                    staged[archive.bdt_path],
                    archive.bdt_path,
                    staged_identities[archive.bdt_path],
                )

            for archive in self.archives:
                if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                    raise BackupError(
                        f"{archive.bhd_path.name} è cambiato durante il ripristino."
                    )
                expected = records[archive.bdt_path.name]["sha256"]
                if _sha256_if_file(archive.bdt_path) != expected:
                    raise BackupError(
                        f"La verifica finale è fallita per {archive.bdt_path.name}."
                    )

            completed = copy.deepcopy(working)
            for record in completed["archives"]:
                record.pop("patched_sha256", None)
            completed["state"] = "restored"
            self.save_manifest(completed)
        except Exception as restore_error:
            if transaction_saved:
                try:
                    self.recover_pending(working)
                except Exception as recovery_error:
                    raise BackupError(
                        "Il ripristino è fallito e lo stato precedente non può essere confermato. "
                        "Non aprire il gioco; chiudi Steam e usa la verifica di integrità. "
                        f"Ripristino: {restore_error}; recupero: {recovery_error}"
                    ) from recovery_error
            raise BackupError(
                "Il ripristino è fallito, ma lo stato precedente è stato recuperato: "
                f"{restore_error}"
            ) from restore_error
        finally:
            for live_path, temp in staged.items():
                try:
                    _unlink_owned_regular(temp, staged_identities.get(live_path))
                except OSError as exc:
                    self.log(f"Attenzione: pulizia rimandata per {temp.name}: {exc}")

        # Success is already durable in the manifest.  Cleanup is deliberately
        # best-effort and can never enter the rollback path above.
        try:
            self._cleanup_completed_transaction(completed)
        except (OSError, BackupError) as exc:
            self.log(f"Attenzione: la pulizia finale del ripristino è stata rimandata: {exc}")


class PatchEngine:
    def __init__(
        self,
        game_dir: str | Path,
        log: Callable[[str], None] | None = None,
        backup_root: str | Path | None = None,
        precommit_guard: Callable[[], None] | None = None,
        archive_profile: GameArchiveProfile | None = None,
        archive_profiles: Sequence[GameArchiveProfile] = (),
    ) -> None:
        self.game_dir = Path(game_dir).resolve()
        self.sd_dir = self.game_dir / "sd"
        self.log = log or (lambda _message: None)
        self.backup_root = Path(backup_root) if backup_root is not None else None
        self.precommit_guard = precommit_guard or (lambda: None)
        self.required_archive_profile = archive_profile
        self.known_archive_profiles = tuple(archive_profiles)
        if archive_profile is not None and self.known_archive_profiles:
            raise ValueError(
                "Usa archive_profile per la modalità rigorosa o archive_profiles per il "
                "rilevamento automatico, mai entrambi."
            )
        profile_ids = [item.profile_id for item in self.known_archive_profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("L'elenco dei profili omologati contiene duplicati.")
        quick_signatures = [
            tuple(
                sorted(
                    (
                        archive.stem.casefold(),
                        archive.bhd_sha256,
                        archive.bdt_size,
                    )
                    for archive in profile.archives
                )
            )
            for profile in self.known_archive_profiles
        ]
        if len(quick_signatures) != len(set(quick_signatures)):
            raise ValueError(
                "Due profili omologati hanno la stessa firma rapida di "
                "BHD/dimensione BDT; il catalogo sarebbe ambiguo."
            )
        self.archive_profile: GameArchiveProfile | None = archive_profile
        # ``archive_profiles`` opts into the universal/historical BNK path.
        # A strict single ``archive_profile`` keeps the already-published
        # target-specific payload behavior unchanged.
        self.merge_bnk_from_baseline = bool(self.known_archive_profiles)
        self.structural_fallback = False
        self.archives: tuple[Archive, ...] = ()
        self.entry_by_hash: dict[int, list[EntryTarget]] = {}

    def _recover_missing_bdts_before_load(self) -> None:
        """Recover the crash window where a journalled live name is absent.

        Archive parsing normally needs the BDT to exist.  A power loss between
        ``live -> rollback`` and publishing the staged name is the one valid
        exception, so reconstruct only that exact, hash-authenticated state from
        a pending manifest before the regular strict loader runs.
        """
        backup_root = _ensure_safe_directory_tree(
            self.backup_root or _default_backup_root(),
            label="La radice dei backup",
            create=False,
        )
        game_id = hashlib.sha256(
            _path_identity_text(self.game_dir).encode("utf-8")
        ).hexdigest()[:16]
        game_root = backup_root / game_id
        if not game_root.is_dir():
            return
        pending_states = {
            "staging",
            "preparing_commit",
            "committing",
            "restoring",
            "recovery_required",
        }
        actions: dict[Path, tuple[Path, tuple[int, int], str]] = {}
        with GameOperationLock(backup_root / ".operation.lock"):
            for manifest_path in game_root.glob("*/manifest.json"):
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    if manifest.get("state") not in pending_states:
                        continue
                    if Path(manifest.get("game_dir", "")).resolve() != self.game_dir:
                        continue
                    transaction = manifest.get("transaction")
                    if not isinstance(transaction, dict):
                        continue
                    transaction_id = transaction.get("id")
                    if not isinstance(transaction_id, str) or not re.fullmatch(
                        r"[0-9a-f]{32}", transaction_id
                    ):
                        continue
                    pre_hashes = transaction.get("pre_sha256") or {}
                    rollback_names = transaction.get("rollback_files") or {}
                    records = {
                        record.get("bdt"): record
                        for record in manifest.get("archives", [])
                        if isinstance(record, dict)
                    }
                except (
                    OSError,
                    json.JSONDecodeError,
                    AttributeError,
                    TypeError,
                    ValueError,
                ):
                    continue
                for name, expected_pre in pre_hashes.items():
                    if not isinstance(name, str) or not re.fullmatch(
                        r"sd(?:_dlc\d+)?\.bdt", name, re.IGNORECASE
                    ):
                        continue
                    if not isinstance(expected_pre, str) or not re.fullmatch(
                        r"[0-9a-f]{64}", expected_pre
                    ):
                        continue
                    live_path = self.sd_dir / name
                    if os.path.lexists(live_path):
                        continue
                    record = records.get(name)
                    if not isinstance(record, dict):
                        continue
                    bhd_name = record.get("bhd")
                    if not isinstance(bhd_name, str) or Path(bhd_name).name != bhd_name:
                        continue
                    bhd_path = self.sd_dir / bhd_name
                    if not bhd_path.is_file() or sha256_file(bhd_path) != record.get(
                        "bhd_sha256"
                    ):
                        continue
                    rollback_name = rollback_names.get(name)
                    expected_name = f".erita-{transaction_id}-{name}.rollback"
                    if (
                        rollback_name != expected_name
                        or not TRANSACTION_FILE_RE.fullmatch(rollback_name)
                    ):
                        continue
                    rollback_path = self.sd_dir / rollback_name
                    try:
                        rollback_identity = _regular_file_identity(
                            rollback_path, label="Il rollback del journal"
                        )
                    except BackupError:
                        if os.path.lexists(rollback_path):
                            raise
                        continue
                    if (
                        _sha256_owned_regular(rollback_path, rollback_identity)
                        != expected_pre
                    ):
                        continue
                    if live_path in actions and actions[live_path][0] != rollback_path:
                        raise BackupError(
                            f"Più di un journal tenta di recuperare {name}; usa la verifica di Steam."
                        )
                    actions[live_path] = (
                        rollback_path,
                        rollback_identity,
                        expected_pre,
                    )

            for live_path, (
                rollback_path,
                rollback_identity,
                expected_pre,
            ) in actions.items():
                if (
                    _sha256_owned_regular(rollback_path, rollback_identity)
                    != expected_pre
                ):
                    raise BackupError(
                        f"Il rollback è cambiato prima di recuperare {live_path.name}."
                    )
                _publish_owned_without_replace(
                    rollback_path, live_path, rollback_identity
                )
                if _sha256_owned_regular(live_path, rollback_identity) != expected_pre:
                    try:
                        _publish_owned_without_replace(
                            live_path, rollback_path, rollback_identity
                        )
                    finally:
                        raise BackupError(
                            f"Il rollback è cambiato durante il recupero di {live_path.name}."
                        )
                self.log(
                    f"Nome attivo recuperato dal journal prima della lettura: {live_path.name}."
                )

    def load_archives(self) -> int:
        if not self.sd_dir.is_dir():
            raise CompatibilityError(f"Cartella audio non trovata: {self.sd_dir}")
        # Un'interruzione di corrente può lasciare momentaneamente assente il nome
        # attivo. Recupera solo questo stato autenticato dal journal prima di
        # richiedere il profilo rapido; altrimenti la protezione di compatibilità
        # impedirebbe proprio il ripristino sicuro che deve preservare.
        self._recover_missing_bdts_before_load()
        if self.required_archive_profile is not None:
            validate_game_archive_profile(
                self.game_dir,
                self.required_archive_profile,
            )
        archives: list[Archive] = []
        entry_map: dict[int, list[EntryTarget]] = {}
        candidates = sorted(
            path
            for path in self.sd_dir.glob("sd*.bhd")
            if ARCHIVE_NAME_RE.fullmatch(path.name)
        )
        for bhd_path in candidates:
            bdt_path = bhd_path.with_suffix(".bdt")
            try:
                bdt_metadata = bdt_path.lstat()
            except OSError as exc:
                raise CompatibilityError(
                    f"Coppia mancante per {bhd_path.name}: {bdt_path.name}."
                ) from exc
            if (
                _metadata_is_link_or_reparse(bdt_metadata)
                or not stat.S_ISREG(bdt_metadata.st_mode)
                or bdt_metadata.st_nlink != 1
            ):
                raise CompatibilityError(
                    f"{bdt_path.name} non è un file regolare esclusivo."
                )
            bdt_size = bdt_metadata.st_size
            bdt_mtime_ns = bdt_metadata.st_mtime_ns
            self.log(f"Lettura di {bhd_path.name} in corso...")
            encrypted = _read_regular_file_limited(
                bhd_path,
                max_size=MAX_BHD_FILE_SIZE,
                label=f"L'indice {bhd_path.name}",
            )
            rsa_encrypted_bhd = not encrypted.startswith(b"BHD5")
            if not rsa_encrypted_bhd:
                decrypted = encrypted
            else:
                if not encrypted or len(encrypted) % 256:
                    raise CompatibilityError(
                        f"{bhd_path.name} non è né BHD5 semplice né RSA in blocchi da 256 byte."
                    )
                decrypted = rsa_decrypt_bhd(encrypted)
            entries = parse_bhd5(decrypted, bdt_size=bdt_size)
            archive = Archive(
                bhd_path=bhd_path,
                bdt_path=bdt_path,
                bhd_sha256=hashlib.sha256(encrypted).hexdigest(),
                bdt_size=bdt_size,
                bdt_mtime_ns=bdt_mtime_ns,
                entries=entries,
                salt=parse_bhd5_salt(decrypted),
                rsa_encrypted_bhd=rsa_encrypted_bhd,
            )
            archives.append(archive)
            for entry in entries:
                entry_map.setdefault(entry.file_name_hash, []).append(
                    EntryTarget(archive, entry)
                )
            self.log(f"  {bhd_path.name}: {len(entries)} voci valide")
        if not archives:
            raise CompatibilityError(
                "Nessuna coppia sd*.bhd/sd*.bdt compatibile è stata trovata."
            )
        if self.required_archive_profile is not None:
            expected = {
                item.stem.casefold(): item
                for item in self.required_archive_profile.archives
            }
            observed = {
                item.bdt_path.stem.casefold(): item for item in archives
            }
            if set(observed) != set(expected) or any(
                observed[stem].bhd_sha256 != fingerprint.bhd_sha256
                or observed[stem].bdt_size != fingerprint.bdt_size
                for stem, fingerprint in expected.items()
            ):
                raise CompatibilityError(
                    "Gli archivi sono cambiati durante la convalida del profilo "
                    f"{self.required_archive_profile.profile_id}."
                )
            self.archive_profile = self.required_archive_profile
            self.structural_fallback = False
        else:
            self.archive_profile = next(
                (
                    profile
                    for profile in self.known_archive_profiles
                    if self._archives_match_profile(archives, profile)
                ),
                None,
            )
            self.structural_fallback = bool(self.known_archive_profiles) and (
                self.archive_profile is None
            )
            if self.structural_fallback:
                plaintext_indexes = sorted(
                    archive.bhd_path.name
                    for archive in archives
                    if not archive.rsa_encrypted_bhd
                )
                if plaintext_indexes:
                    raise CompatibilityError(
                        "Questo build non è ancora catalogato e usa un indice BHD "
                        "senza l'involucro RSA ufficiale: "
                        f"{', '.join(plaintext_indexes)}. La modalità strutturale non "
                        "accetta un indice autocoerente creato localmente. "
                        "Nessun file è stato modificato."
                    )
                unauthenticated_entries = sum(
                    entry.sha_info is None
                    or not any(
                        item.start_offset >= 0
                        and item.end_offset > item.start_offset
                        for item in entry.sha_info.ranges
                    )
                    for archive in archives
                    for entry in archive.entries
                )
                if unauthenticated_entries:
                    raise CompatibilityError(
                        "Questo build non è ancora catalogato e ha "
                        f"{unauthenticated_entries} voci senza SHA salted nel BHD. "
                        "L'analisi automatica non può autorizzare l'installazione in "
                        "sicurezza. Nessun file è stato modificato."
                    )
                self.log(
                    "Build non catalogato: uso la compatibilità strutturale "
                    "adattiva e i range SHA salted disponibili nell'indice."
                )
            elif self.archive_profile is not None:
                self.log(
                    "Profilo omologato riconosciuto: "
                    f"{self.archive_profile.profile_id}."
                )
        self.archives = tuple(archives)
        self.entry_by_hash = entry_map
        return sum(len(item.entries) for item in archives)

    @staticmethod
    def _archives_match_profile(
        archives: Sequence[Archive],
        profile: GameArchiveProfile,
    ) -> bool:
        expected = {item.stem.casefold(): item for item in profile.archives}
        observed = {item.bdt_path.stem.casefold(): item for item in archives}
        return set(observed) == set(expected) and all(
            observed[stem].bhd_sha256 == fingerprint.bhd_sha256
            and observed[stem].bdt_size == fingerprint.bdt_size
            for stem, fingerprint in expected.items()
        )

    @staticmethod
    def _candidate_game_paths(relative: str, suffix: str, stem: str) -> tuple[str, ...]:
        values = [relative]
        if not relative.lower().startswith("enus/"):
            values.append(f"enus/{relative}")
        if suffix == ".wem" and stem.isdigit() and len(stem) >= 2:
            values.append(f"enus/wem/{stem[:2]}/{stem}.wem")
        return tuple(
            dict.fromkeys(item.replace("\\", "/").strip("/") for item in values)
        )

    def build_plan(
        self,
        payload_dir: str | Path,
        min_match_ratio: float = MIN_MATCH_RATIO,
        progress: Callable[[int, int], None] | None = None,
    ) -> PatchPlan:
        if not self.archives:
            raise PatcherError("I file del gioco non sono ancora stati caricati.")
        payload_root = Path(payload_dir).resolve()
        if not payload_root.is_dir():
            raise CompatibilityError(f"Cartella del payload inesistente: {payload_root}")
        files = sorted(
            (
                path
                for path in payload_root.rglob("*")
                if path.is_file() and path.suffix.lower() in {".wem", ".bnk"}
            ),
            key=lambda item: item.as_posix().casefold(),
        )
        if not files:
            raise CompatibilityError("Il pacchetto non contiene file WEM/BNK.")

        replacements: list[Replacement] = []
        unmatched: list[str] = []
        for source in files:
            relative = source.relative_to(payload_root).as_posix()
            selected: tuple[str, int, list[EntryTarget]] | None = None
            for game_path in self._candidate_game_paths(
                relative, source.suffix.lower(), source.stem
            ):
                file_hash = hash_path(game_path)
                targets = self.entry_by_hash.get(file_hash)
                if targets:
                    selected = (game_path, file_hash, targets)
                    break
            if selected is None:
                unmatched.append(relative)
                continue
            game_path, file_hash, targets = selected
            replacements.append(
                Replacement(
                    source_path=source,
                    source_relative=relative,
                    game_path=game_path,
                    file_hash=file_hash,
                    targets=tuple(targets),
                )
            )

        ratio = len(replacements) / len(files)
        if ratio < min_match_ratio:
            raise CompatibilityError(
                "Questa build del gioco non corrisponde al pacchetto di doppiaggio: "
                f"{len(replacements)}/{len(files)} file trovati ({ratio:.1%}); "
                f"il minimo sicuro è {min_match_ratio:.0%}. Nessun file è stato modificato."
            )

        writes_by_target: dict[tuple[Path, int], PreparedWrite] = {}
        payload_file_sha256: dict[str, str] = {}
        total_targets = sum(len(item.targets) for item in replacements)
        done = 0
        for replacement in replacements:
            source_data = replacement.source_path.read_bytes()
            source_digest = hashlib.sha256(source_data).hexdigest()
            payload_file_sha256[replacement.source_relative] = source_digest
            for target in replacement.targets:
                dynamic_bnk = (
                    self.merge_bnk_from_baseline
                    and replacement.source_path.suffix.lower() == ".bnk"
                )
                prepared_slot: bytes | None = None
                if not dynamic_bnk:
                    try:
                        prepared_slot = prepare_slot(
                            source_data,
                            replacement.source_path.suffix,
                            target.entry,
                        )
                    except CompatibilityError as exc:
                        raise CompatibilityError(
                            f"Payload incompatibile in {replacement.source_relative} per "
                            f"{target.archive.bdt_path.name}: {exc} Nessun file è stato modificato."
                        ) from exc
                candidate = PreparedWrite(replacement, target, source_digest)
                key = (target.archive.bdt_path, target.entry.file_offset)
                previous = writes_by_target.get(key)
                if previous is None:
                    writes_by_target[key] = candidate
                else:
                    if previous.target.entry != target.entry:
                        raise CompatibilityError(
                            "Due file del payload tentano di scrivere sullo stesso offset "
                            "con metadati di slot diversi: "
                            f"{previous.replacement.source_relative} e "
                            f"{replacement.source_relative}. Nessun file è stato modificato."
                        )
                    if (
                        previous.replacement.source_path.suffix.lower()
                        != replacement.source_path.suffix.lower()
                    ):
                        raise CompatibilityError(
                            "Due tipi di payload tentano di scrivere nello stesso slot: "
                            f"{previous.replacement.source_relative} e "
                            f"{replacement.source_relative}. Nessun file è stato modificato."
                        )
                    previous_data = previous.replacement.source_path.read_bytes()
                    if (
                        hashlib.sha256(previous_data).hexdigest()
                        != previous.source_sha256
                    ):
                        raise CompatibilityError(
                            "Il payload è cambiato durante la pianificazione: "
                            f"{previous.replacement.source_relative}. "
                            "Nessun file è stato modificato."
                        )
                    if previous_data != source_data:
                        raise CompatibilityError(
                            "Due file del payload tentano di scrivere contenuti diversi "
                            "nello stesso slot: "
                            f"{previous.replacement.source_relative} e "
                            f"{replacement.source_relative}. Nessun file è stato modificato."
                        )
                    if not dynamic_bnk:
                        try:
                            previous_slot = prepare_slot(
                                previous_data,
                                previous.replacement.source_path.suffix,
                                previous.target.entry,
                            )
                        except CompatibilityError as exc:
                            raise CompatibilityError(
                                "Payload incompatibile in "
                                f"{previous.replacement.source_relative} per "
                                f"{target.archive.bdt_path.name}: {exc} "
                                "Nessun file è stato modificato."
                            ) from exc
                        if previous_slot != prepared_slot:
                            raise CompatibilityError(
                                "Due file del payload tentano di scrivere contenuti diversi "
                                "nello stesso slot: "
                                f"{previous.replacement.source_relative} e "
                                f"{replacement.source_relative}. Nessun file è stato modificato."
                            )

                    # Il payload storico ha alcuni alias nella radice e in
                    # enus/. Quando i byte preparati sono identici, mantieni
                    # il nome che coincide esattamente con il percorso indicizzato nel
                    # gioco. Verrà comunque eseguita una sola scrittura in questo slot.
                    previous_is_canonical = (
                        previous.replacement.source_relative.casefold()
                        == previous.replacement.game_path.casefold()
                    )
                    candidate_is_canonical = (
                        replacement.source_relative.casefold()
                        == replacement.game_path.casefold()
                    )
                    if candidate_is_canonical and not previous_is_canonical:
                        writes_by_target[key] = candidate
                done += 1
                if progress:
                    progress(done, total_targets)

        # L'autenticazione successiva richiede l'identità dell'intero albero, anche
        # per un file senza target in una build che soddisfi comunque la copertura
        # minima. I file corrispondenti sono già stati letti sopra.
        for source in files:
            relative = source.relative_to(payload_root).as_posix()
            if relative not in payload_file_sha256:
                payload_file_sha256[relative] = hashlib.sha256(
                    source.read_bytes()
                ).hexdigest()

        writes = sorted(
            writes_by_target.values(),
            key=lambda item: (
                str(item.target.archive.bdt_path).casefold(),
                item.target.entry.file_offset,
                item.replacement.source_relative.casefold(),
            ),
        )

        # Una collisione parziale sarebbe ancora più pericolosa di una collisione di offset
        # esatta: valida la mappa completa prima di creare qualsiasi backup/staging.
        by_archive: dict[Path, list[PreparedWrite]] = {}
        for write in writes:
            by_archive.setdefault(write.target.archive.bdt_path, []).append(write)
        for archive_path, archive_writes in by_archive.items():
            ordered = sorted(
                archive_writes, key=lambda item: item.target.entry.file_offset
            )
            previous_end = -1
            previous_name = ""
            for write in ordered:
                entry = write.target.entry
                if entry.file_offset < previous_end:
                    raise CompatibilityError(
                        f"Slot sovrapposti in {archive_path.name}: {previous_name} e "
                        f"{write.replacement.source_relative}. Nessun file è stato modificato."
                    )
                previous_end = entry.file_offset + entry.padded_file_size
                previous_name = write.replacement.source_relative
        return PatchPlan(
            writes=tuple(writes),
            payload_file_count=len(files),
            matched_file_count=len(replacements),
            unmatched_files=tuple(unmatched),
            payload_file_sha256=tuple(
                sorted(payload_file_sha256.items(), key=lambda item: item[0].casefold())
            ),
        )

    def _backup_manager(self, archives: Sequence[Archive]) -> BackupManager:
        expected_original: dict[str, str] | None = None
        if self.archive_profile is not None:
            profile_hashes = {
                f"{item.stem}.bdt".casefold(): item.original_bdt_sha256
                for item in self.archive_profile.archives
            }
            expected_original = {
                archive.bdt_path.name: profile_hashes[archive.bdt_path.name.casefold()]
                for archive in archives
            }
        return BackupManager(
            self.game_dir,
            archives,
            backup_root=self.backup_root,
            log=self.log,
            precommit_guard=self.precommit_guard,
            expected_original_sha256=expected_original,
        )

    def apply_plan(
        self,
        plan: PatchPlan,
        progress: Callable[[int, int], None] | None = None,
        *,
        bhd_integrity_mode: str = BHD_INTEGRITY_STRICT,
    ) -> tuple[int, int]:
        if not plan.writes:
            raise CompatibilityError("Il piano di patch è vuoto.")
        # The baseline always covers every loaded sd archive, even if this
        # particular payload writes only a subset.  A later payload expansion
        # can therefore never mistake already dubbed bytes for game originals.
        manager = self._backup_manager(self.archives)
        with manager.operation_lock():
            return self._apply_plan_locked(
                plan,
                manager,
                progress,
                bhd_integrity_mode=bhd_integrity_mode,
            )

    def _validate_plan_snapshot(self, archives: Sequence[Archive]) -> None:
        for archive in archives:
            if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                raise CompatibilityError(
                    f"{archive.bhd_path.name} è cambiato dopo la pianificazione; riprova."
                )
            current = archive.bdt_path.stat()
            if (
                current.st_size != archive.bdt_size
                or current.st_mtime_ns != archive.bdt_mtime_ns
            ):
                raise CompatibilityError(
                    f"{archive.bdt_path.name} è cambiato dopo la pianificazione; riprova."
                )

    def _apply_plan_locked(
        self,
        plan: PatchPlan,
        manager: BackupManager,
        progress: Callable[[int, int], None] | None,
        *,
        bhd_integrity_mode: str = BHD_INTEGRITY_STRICT,
    ) -> tuple[int, int]:
        self._validate_plan_snapshot(self.archives)
        selected_integrity_mode = _validated_bhd_integrity_mode(bhd_integrity_mode)
        new_baseline_assessment: BHDIntegrityAssessment | None = None

        def authenticate_new_baseline() -> None:
            nonlocal new_baseline_assessment
            new_baseline_assessment = validate_patch_plan_sha_integrity(
                plan,
                archives=self.archives,
                mode=selected_integrity_mode,
                merge_bnk_from_baseline=self.merge_bnk_from_baseline,
                require_entry_sha_metadata=self.structural_fallback,
            )

        manifest, created, pre_hashes = manager.prepare(
            new_baseline_guard=authenticate_new_baseline,
        )
        records = {record["bdt"]: record for record in manifest["archives"]}
        if created:
            if new_baseline_assessment is None:
                raise BackupError(
                    "Il nuovo baseline non è stato autenticato prima della pubblicazione."
                )
            integrity_assessment = new_baseline_assessment
        else:
            integrity_assessment = validate_patch_plan_sha_integrity(
                plan,
                archives=self.archives,
                mode=selected_integrity_mode,
                baseline_paths={
                    archive.bdt_path: manager.directory
                    / records[archive.bdt_path.name]["backup"]
                    for archive in self.archives
                },
                merge_bnk_from_baseline=self.merge_bnk_from_baseline,
                require_entry_sha_metadata=self.structural_fallback,
            )
        newly_touched = {archive.bdt_path for archive in plan.touched_archives}
        previously_patched = {
            record["bdt"]
            for record in manifest["archives"]
            if isinstance(record.get("patched_sha256"), str)
        }
        # Rebuild from the immutable baseline any archive patched by the prior
        # payload even if the new payload no longer contains a write for it.
        archives_to_stage = tuple(
            archive
            for archive in self.archives
            if archive.bdt_path in newly_touched
            or archive.bdt_path.name in previously_patched
        )
        staging_needed = (
            sum(item.bdt_size for item in archives_to_stage) + 64 * 1024 * 1024
        )
        staging_free = shutil.disk_usage(self.sd_dir).free
        if staging_free < staging_needed:
            raise BackupError(
                "Spazio insufficiente sul disco del gioco per preparare l'installazione atomica: "
                f"necessario {staging_needed / (1024**3):.2f} GiB; "
                f"disponibile {staging_free / (1024**3):.2f} GiB."
            )

        transaction_id = uuid.uuid4().hex
        transaction = {
            "id": transaction_id,
            "kind": "apply",
            "previous_state": manifest.get("state", "prepared"),
            "pre_sha256": {
                archive.bdt_path.name: pre_hashes[archive.bdt_path]
                for archive in archives_to_stage
            },
            "previous_patched_sha256": {
                record["bdt"]: record.get("patched_sha256")
                for record in manifest["archives"]
            },
            "new_sha256": {},
            "rollback_files": {
                archive.bdt_path.name: (
                    f".erita-{transaction_id}-{archive.bdt_path.name}.rollback"
                )
                for archive in archives_to_stage
            },
            "displaced_files": {
                archive.bdt_path.name: (
                    f".erita-{transaction_id}-{archive.bdt_path.name}.displaced"
                )
                for archive in archives_to_stage
            },
        }
        manifest["transaction"] = transaction
        manifest["state"] = "staging"
        manager.save_manifest(manifest)

        stage_by_live: dict[Path, Path] = {}
        stage_identity_by_live: dict[Path, tuple[int, int]] = {}
        rollback_by_live: dict[Path, Path] = {}
        handles: dict[Path, BinaryIO] = {}
        baseline_handles: dict[Path, tuple[BinaryIO, os.stat_result, Path]] = {}
        external_wem_ids = _planned_external_wem_ids(plan)
        try:
            for archive in archives_to_stage:
                record = records[archive.bdt_path.name]
                backup_path = manager.directory / record["backup"]
                stage_path = archive.bdt_path.with_name(
                    f".{archive.bdt_path.name}.erita-stage-{transaction_id}.tmp"
                )
                self.log(f"Preparazione della copia transazionale di {archive.bdt_path.name} in corso...")
                copied_digest = _copy_with_sha256(backup_path, stage_path)
                if copied_digest != record["sha256"]:
                    raise BackupError(
                        f"Copia di staging corrotta per {archive.bdt_path.name}."
                    )
                stage_identity = _regular_file_identity(
                    stage_path, label="La copia di staging"
                )
                stage_by_live[archive.bdt_path] = stage_path
                stage_identity_by_live[archive.bdt_path] = stage_identity
                handles[archive.bdt_path] = _open_owned_regular_for_update(
                    stage_path, stage_identity, label="La copia di staging"
                )
                baseline_stream, baseline_opened = _open_bdt_for_integrity(
                    backup_path,
                    expected_size=archive.bdt_size,
                    label=f"Il baseline di {archive.bdt_path.name}",
                )
                baseline_handles[archive.bdt_path] = (
                    baseline_stream,
                    baseline_opened,
                    backup_path,
                )
            for index, write in enumerate(plan.writes, start=1):
                source_data = write.replacement.source_path.read_bytes()
                if hashlib.sha256(source_data).hexdigest() != write.source_sha256:
                    raise PatcherError(
                        f"Il payload è cambiato durante l'installazione: {write.replacement.source_relative}."
                    )
                baseline_stream = baseline_handles[
                    write.target.archive.bdt_path
                ][0]
                slot = _materialize_prepared_slot(
                    source_data,
                    write.replacement.source_path.suffix,
                    write.target.entry,
                    baseline_stream=baseline_stream,
                    archive_name=write.target.archive.bdt_path.name,
                    external_wem_ids=external_wem_ids,
                    merge_bnk_from_baseline=self.merge_bnk_from_baseline,
                )
                stream = handles[write.target.archive.bdt_path]
                stream.seek(write.target.entry.file_offset)
                written = stream.write(slot)
                if written != len(slot):
                    raise OSError(
                        f"Scrittura incompleta in {write.target.archive.bdt_path.name}: "
                        f"{written}/{len(slot)} byte."
                    )
                if progress:
                    progress(index, len(plan.writes))
            for stream in handles.values():
                stream.flush()
                os.fsync(stream.fileno())

            # Rileggi ogni slot dello staging. Il successo viene mostrato solo se ogni byte
            # corrisponde a quanto pianificato.
            self.log("Verifica dei file preparati in corso...")
            for index, write in enumerate(plan.writes, start=1):
                source_data = write.replacement.source_path.read_bytes()
                if hashlib.sha256(source_data).hexdigest() != write.source_sha256:
                    raise PatcherError(
                        "Il payload è cambiato prima della verifica dello staging: "
                        f"{write.replacement.source_relative}."
                    )
                baseline_stream = baseline_handles[
                    write.target.archive.bdt_path
                ][0]
                expected = _materialize_prepared_slot(
                    source_data,
                    write.replacement.source_path.suffix,
                    write.target.entry,
                    baseline_stream=baseline_stream,
                    archive_name=write.target.archive.bdt_path.name,
                    external_wem_ids=external_wem_ids,
                    merge_bnk_from_baseline=self.merge_bnk_from_baseline,
                )
                stream = handles[write.target.archive.bdt_path]
                stream.seek(write.target.entry.file_offset)
                actual = stream.read(len(expected))
                if actual != expected:
                    raise OSError(
                        f"La verifica è fallita in {write.target.archive.bdt_path.name}, "
                        f"slot {write.replacement.source_relative}."
                    )
            for archive in archives_to_stage:
                baseline_stream, baseline_opened, backup_path = baseline_handles[
                    archive.bdt_path
                ]
                _require_open_bdt_unchanged(
                    backup_path,
                    baseline_stream,
                    baseline_opened,
                    expected_size=archive.bdt_size,
                    label=f"Il baseline di {archive.bdt_path.name}",
                )
            for stream in handles.values():
                stream.close()
            handles.clear()
            for baseline_stream, _opened, _path in baseline_handles.values():
                baseline_stream.close()
            baseline_handles.clear()

            staged_assessment = validate_staged_patch_sha_integrity(
                plan,
                archives_to_stage,
                baseline_paths={
                    archive.bdt_path: manager.directory
                    / records[archive.bdt_path.name]["backup"]
                    for archive in archives_to_stage
                },
                staging_paths=stage_by_live,
                expected_divergent_entries=(
                    integrity_assessment.divergent_entries
                ),
                staging_identities=stage_identity_by_live,
                merge_bnk_from_baseline=self.merge_bnk_from_baseline,
                require_entry_sha_metadata=self.structural_fallback,
            )
            validated_stage_sha256 = dict(
                staged_assessment.validated_archive_sha256
            )
            validated_stage_identities = dict(
                staged_assessment.validated_archive_identities
            )

            for archive in archives_to_stage:
                record = records[archive.bdt_path.name]
                expected_identity = validated_stage_identities.get(archive.bdt_path)
                expected_digest = validated_stage_sha256.get(archive.bdt_path)
                if (
                    expected_identity != stage_identity_by_live[archive.bdt_path]
                    or not isinstance(expected_digest, str)
                ):
                    raise CompatibilityError(
                        f"La verifica dello staging di {archive.bdt_path.name} "
                        "non ha restituito un'autorità completa."
                    )
                digest = _sha256_owned_regular(
                    stage_by_live[archive.bdt_path],
                    stage_identity_by_live[archive.bdt_path],
                )
                if digest != expected_digest:
                    raise CompatibilityError(
                        f"Lo staging di {archive.bdt_path.name} è cambiato dopo la "
                        "verifica esatta."
                    )
                if archive.bdt_path in newly_touched:
                    record["patched_sha256"] = expected_digest
                else:
                    record.pop("patched_sha256", None)
                transaction["new_sha256"][archive.bdt_path.name] = expected_digest

            # Steam, un altro patcher o il gioco non possono sostituire i file tra
            # la pianificazione e il commit.
            for archive in archives_to_stage:
                if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                    raise CompatibilityError(
                        f"{archive.bhd_path.name} è cambiato durante l'installazione; operazione annullata."
                    )
                live_stat = archive.bdt_path.stat()
                if live_stat.st_size != archive.bdt_size:
                    raise CompatibilityError(
                        f"{archive.bdt_path.name} è cambiato durante l'installazione; operazione annullata."
                    )
                current_hash = sha256_file(archive.bdt_path)
                if current_hash != pre_hashes[archive.bdt_path]:
                    raise CompatibilityError(
                        f"{archive.bdt_path.name} è cambiato durante l'installazione; il file esterno "
                        "sarà preservato e l'operazione è stata annullata."
                    )

            # Reserve and validate every journal path before moving a live BDT.
            for archive in archives_to_stage:
                rollback_name, displaced_name = manager._transaction_names(
                    transaction, archive
                )
                rollback_path = manager._transaction_path(rollback_name)
                displaced_path = manager._transaction_path(displaced_name)
                if rollback_path.exists() or displaced_path.exists():
                    raise BackupError(
                        f"Il file di transazione esiste già per {archive.bdt_path.name}."
                    )
                rollback_by_live[archive.bdt_path] = rollback_path

            # Baseline creation and staging can take minutes.  Re-run the UI's
            # process/build guard at the last safe point before the journalled swap.
            self.precommit_guard()
            manifest["state"] = "preparing_commit"
            manager.save_manifest(manifest)
            manifest["state"] = "committing"
            manager.save_manifest(manifest)
            for archive in archives_to_stage:
                live_path = archive.bdt_path
                rollback_path = rollback_by_live[live_path]
                if (
                    _regular_file_identity(
                        stage_by_live[live_path], label="La copia di staging"
                    )
                    != stage_identity_by_live[live_path]
                ):
                    raise BackupError(
                        f"La copia di staging è stata sostituita per {live_path.name}."
                    )
                _publish_without_replace(live_path, rollback_path)
                # Hash after the move closes the check/swap race: any replacement
                # made by Steam is now preserved under the rollback name.
                if sha256_file(rollback_path) != pre_hashes[live_path]:
                    try:
                        _publish_without_replace(rollback_path, live_path)
                    finally:
                        raise CompatibilityError(
                            f"{live_path.name} è cambiato nell'istante dello scambio; "
                            "il file trovato è stato preservato."
                        )
                _publish_owned_without_replace(
                    stage_by_live[live_path],
                    live_path,
                    stage_identity_by_live[live_path],
                )

            for archive in archives_to_stage:
                if sha256_file(archive.bhd_path) != archive.bhd_sha256:
                    raise CompatibilityError(
                        f"{archive.bhd_path.name} è cambiato durante la verifica finale."
                    )
                expected_new = transaction["new_sha256"][archive.bdt_path.name]
                if _sha256_if_file(archive.bdt_path) != expected_new:
                    raise CompatibilityError(
                        f"{archive.bdt_path.name} è cambiato durante la verifica finale; "
                        "nessun successo verrà annunciato."
                    )

            completed = copy.deepcopy(manifest)
            completed["state"] = "applied"
            manager.save_manifest(completed)
            cleanup_complete = True
            for live_path, rollback_path in rollback_by_live.items():
                record = records[live_path.name]
                known = {
                    value
                    for value in (
                        transaction["pre_sha256"].get(live_path.name),
                        transaction["new_sha256"].get(live_path.name),
                        record.get("sha256"),
                    )
                    if isinstance(value, str)
                }
                cleanup_complete &= manager._discard_known_transaction_file(
                    rollback_path, known
                )
            if cleanup_complete:
                completed.pop("transaction", None)
                try:
                    manager.save_manifest(completed)
                except (OSError, BackupError) as cleanup_error:
                    # Il manifesto 'applied' precedente è sufficiente per recuperare
                    # o pulire alla prossima apertura.
                    self.log(f"Attenzione: pulizia del journal rimandata: {cleanup_error}")
            return len(plan.writes), len(plan.unmatched_files)
        except Exception as patch_error:
            self.log(f"Errore durante la scrittura: {patch_error}")
            for stream in handles.values():
                try:
                    stream.close()
                except Exception:
                    pass
            handles.clear()
            for baseline_stream, _opened, _path in baseline_handles.values():
                try:
                    baseline_stream.close()
                except Exception:
                    pass
            baseline_handles.clear()
            self.log("Ritorno allo stato esatto precedente a questo tentativo...")
            try:
                manager.recover_pending(manifest)
            except Exception as restore_error:
                raise BackupError(
                    "La patch è fallita e non è stato possibile confermare lo stato precedente. "
                    "Usa la verifica di integrità di Steam prima di aprire il gioco. "
                    f"Patch: {patch_error}; recupero: {restore_error}"
                ) from restore_error
            raise PatcherError(
                f"La patch è fallita, ma lo stato precedente è stato ripristinato: {patch_error}"
            ) from patch_error
        finally:
            for stream in handles.values():
                try:
                    stream.close()
                except Exception:
                    pass
            for baseline_stream, _opened, _path in baseline_handles.values():
                try:
                    baseline_stream.close()
                except Exception:
                    pass
            for live_path, stage_path in stage_by_live.items():
                try:
                    _unlink_owned_regular(
                        stage_path, stage_identity_by_live.get(live_path)
                    )
                except OSError:
                    pass

    def restore_current_backup(self) -> None:
        if not self.archives:
            raise PatcherError("I file del gioco non sono ancora stati caricati.")
        probe = self._backup_manager(self.archives)
        with probe.operation_lock():
            self._restore_current_backup_locked(probe)

    def _restore_current_backup_locked(self, probe: BackupManager) -> None:
        probe.assert_no_foreign_pending()
        game_root = probe.backup_root / probe.game_id
        archive_by_names = {
            (item.bhd_path.name, item.bdt_path.name): item for item in self.archives
        }
        pending_states = {
            "applying",
            "staging",
            "preparing_commit",
            "committing",
            "restoring",
            "recovery_required",
        }
        candidates: list[tuple[bool, int, str, BackupManager]] = []
        unsafe_manifests: list[Path] = []
        if game_root.is_dir():
            for manifest_path in game_root.glob("*/manifest.json"):
                try:
                    value = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    unsafe_manifests.append(manifest_path)
                    continue
                if not isinstance(value, dict):
                    unsafe_manifests.append(manifest_path)
                    continue
                is_pending = value.get("state") in pending_states or isinstance(
                    value.get("transaction"), dict
                )
                try:
                    selected = tuple(
                        archive_by_names[(record["bhd"], record["bdt"])]
                        for record in value.get("archives", [])
                    )
                except (KeyError, TypeError):
                    if is_pending:
                        unsafe_manifests.append(manifest_path)
                    continue
                if not selected:
                    if is_pending:
                        unsafe_manifests.append(manifest_path)
                    continue
                manager = self._backup_manager(selected)
                if manager.manifest_path != manifest_path:
                    if is_pending:
                        unsafe_manifests.append(manifest_path)
                    continue
                candidates.append(
                    (
                        is_pending,
                        len(selected),
                        value.get("created_at")
                        if isinstance(value.get("created_at"), str)
                        else "",
                        manager,
                    )
                )
        pending_candidates = [item for item in candidates if item[0]]
        if unsafe_manifests or len(pending_candidates) > 1:
            details = ", ".join(path.parent.name for path in unsafe_manifests)
            raise BackupError(
                "Esiste un journal di backup che non può essere associato in modo sicuro "
                f"alla build attuale ({details or 'più transazioni'}). Non aprire il gioco; "
                "usa la verifica di integrità di Steam."
            )
        for _pending, _count, _created_at, manager in sorted(
            candidates, reverse=True, key=lambda item: item[:3]
        ):
            manager.restore()
            return
        raise BackupError(
            "Non esiste un backup sicuro per questa build del gioco. Se il gioco è stato aggiornato, "
            "usa 'Verifica integrità dei file' nelle proprietà del gioco su Steam."
        )


def validate_game_directory(path: str | Path) -> Path:
    game_dir = Path(path).expanduser().resolve()
    if not (game_dir / "eldenring.exe").is_file():
        raise CompatibilityError(
            "Seleziona la cartella 'ELDEN RING/Game' che contiene eldenring.exe."
        )
    if not (game_dir / "sd" / "sd.bhd").is_file():
        raise CompatibilityError("Il file sd/sd.bhd non è stato trovato.")
    return game_dir


def find_incomplete_backups(backup_root: Path | None = None) -> Iterable[Path]:
    """Elenca i manifesti lasciati in stati transazionali per la diagnostica."""
    root = _ensure_safe_directory_tree(
        backup_root or _default_backup_root(),
        label="La radice dei backup",
        create=False,
    )
    if not root.is_dir():
        return ()
    result: list[Path] = []
    for manifest_path in _iter_backup_manifest_paths(root):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # An unreadable/truncated journal is itself a reason to warn before
            # the user opens the game. Atomic writes make this rare, not safe.
            result.append(manifest_path)
            continue
        if not isinstance(data, dict):
            result.append(manifest_path)
            continue
        if data.get("state") in {
            "applying",
            "staging",
            "preparing_commit",
            "committing",
            "restoring",
            "recovery_required",
        } or isinstance(data.get("transaction"), dict):
            result.append(manifest_path)
    return tuple(result)
