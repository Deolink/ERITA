"""Secure acquisition and extraction of ERPT-BR's audio payload.

Only data is downloaded by this module.  The archive URL, byte length and
SHA-256 are pinned, so a GitHub release (or a local file with the same name)
cannot silently replace executable Python code.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import struct
import tempfile
from typing import BinaryIO, Callable, ContextManager, Iterable, Mapping
import urllib.parse
import urllib.request
import uuid
import zipfile


PAYLOAD_VERSION = "v0.8.1"
PAYLOAD_ARCHIVE_NAME = "patch_data_v081.zip"
PAYLOAD_URL = (
    "https://github.com/lorepamplona/ERPT-BR/releases/download/"
    "v0.8.1/patch_data_v081.zip"
)
PAYLOAD_ARCHIVE_SIZE = 587_566_572
PAYLOAD_SHA256 = "d66bb45093e911202f80cebac44650063e27da2cba41a78760b10e4d82d81d0c"
PAYLOAD_TREE_SHA256 = "587533f29239d8dbe2131573e6e86a2452b272e76983f6cfef1a332d7b046417"
PAYLOAD_WEM_COUNT = 8_969
PAYLOAD_BNK_COUNT = 272
PAYLOAD_FILE_COUNT = 9_241
PAYLOAD_UNCOMPRESSED_SIZE = 604_911_847
PAYLOAD_MAX_FILE_SIZE = 74_897_763

MARKER_FILENAME = ".erptbr-payload.json"
MARKER_SCHEMA = 2
DOWNLOAD_CHUNK_SIZE = 1024 * 1024

LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]
UrlOpener = Callable[..., ContextManager[BinaryIO]]


class PatchDataError(RuntimeError):
    """Base class for errors that are safe to show to an end user."""


class PayloadValidationError(PatchDataError):
    """The payload does not match the immutable release manifest."""


class PayloadDownloadError(PatchDataError):
    """The pinned payload could not be downloaded safely."""


class PayloadExtractionError(PatchDataError):
    """A validated archive could not be extracted safely."""


def _metadata_is_link_or_reparse(metadata: os.stat_result) -> bool:
    if stat.S_ISLNK(metadata.st_mode):
        return True
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and file_attributes & reparse_flag)


def _is_link_or_reparse(path: Path) -> bool:
    return _metadata_is_link_or_reparse(path.lstat())


def _absolute_without_resolving(path: str | os.PathLike[str]) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _ensure_safe_directory_tree(path: str | os.PathLike[str], *, label: str) -> Path:
    """Create/validate every lexical component without accepting reparses."""

    target = _absolute_without_resolving(path)
    for current in (*reversed(target.parents), target):
        if os.path.lexists(current):
            try:
                metadata = current.lstat()
            except OSError as exc:
                raise PatchDataError(
                    f"Impossibile ispezionare {label} '{current}': {exc}"
                ) from exc
            if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(
                metadata.st_mode
            ):
                raise PatchDataError(
                    f"{label} contiene link, reparse point o tipo non sicuro: '{current}'."
                )
            continue
        try:
            current.mkdir()
        except FileExistsError:
            pass
        except OSError as exc:
            raise PatchDataError(
                f"Impossibile creare {label} '{current}': {exc}"
            ) from exc
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise PatchDataError(
                f"Impossibile confermare {label} '{current}': {exc}"
            ) from exc
        if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
            raise PatchDataError(
                f"{label} è riapparso come link, reparse point o tipo non sicuro: '{current}'."
            )
    return target


def _open_safe_lock_file(path: Path) -> BinaryIO:
    """Open a one-byte lock without ever writing through an existing link."""

    _ensure_safe_directory_tree(path.parent, label="La cartella del lock di payload")
    before: os.stat_result | None = None
    try:
        stream = path.open("x+b")
    except FileExistsError:
        try:
            before = path.lstat()
        except OSError as exc:
            raise PatchDataError(f"Lock di payload non sicuro: '{path}': {exc}") from exc
        if (
            _metadata_is_link_or_reparse(before)
            or not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
        ):
            raise PatchDataError(
                f"Il lock di payload non è un file regolare esclusivo: '{path}'."
            )
        try:
            stream = path.open("r+b")
        except OSError as exc:
            raise PatchDataError(f"Lock di payload non sicuro: '{path}': {exc}") from exc
    except OSError as exc:
        raise PatchDataError(
            f"Impossibile creare il lock di payload: {exc}"
        ) from exc

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
            raise PatchDataError(f"Il lock di payload è cambiato o possiede un hardlink: '{path}'.")

        # A process killed between exclusive creation and its first write leaves
        # a zero-byte, app-owned lock. Recover that exact inode only after the
        # descriptor/path identity and single-link invariant have been checked.
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
            raise PatchDataError(f"Il lock di payload è cambiato o possiede un hardlink: '{path}'.")
        stream.seek(0)
        return stream
    except Exception:
        stream.close()
        raise


class PayloadCacheLock:
    """Cross-process mutex for download/extraction into one payload cache."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream: BinaryIO | None = None

    def __enter__(self) -> "PayloadCacheLock":
        self._stream = _open_safe_lock_file(self.path)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - the release currently targets Windows
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self._stream.close()
            self._stream = None
            raise PatchDataError(
                "Un'altra istanza di ERPT-BR sta validando il pacchetto audio. "
                "Attendi che l'altra finestra finisca e riprova."
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
            else:  # pragma: no cover - the release currently targets Windows
                import fcntl

                fcntl.flock(self._stream.fileno(), fcntl.LOCK_UN)
        finally:
            self._stream.close()
            self._stream = None


@dataclass(frozen=True, slots=True)
class PayloadSpec:
    """Immutable expectations for one payload archive.

    The constructor is public mainly so tests and future, explicitly reviewed
    payload releases can use small fixtures.  Production callers should rely on
    :data:`PRODUCTION_PAYLOAD`.
    """

    version: str
    archive_name: str
    url: str
    archive_size: int
    sha256: str
    wem_count: int
    bnk_count: int
    uncompressed_size: int
    max_file_size: int
    tree_sha256: str

    def __post_init__(self) -> None:
        digest = self.sha256.lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError("sha256 deve contenere esattamente 64 caratteri esadecimali")
        object.__setattr__(self, "sha256", digest)
        tree_digest = self.tree_sha256.lower()
        if len(tree_digest) != 64 or any(
            char not in "0123456789abcdef" for char in tree_digest
        ):
            raise ValueError(
                "tree_sha256 deve contenere esattamente 64 caratteri esadecimali"
            )
        object.__setattr__(self, "tree_sha256", tree_digest)
        numeric_values = (
            self.archive_size,
            self.wem_count,
            self.bnk_count,
            self.uncompressed_size,
            self.max_file_size,
        )
        if any(value < 0 for value in numeric_values):
            raise ValueError("i limiti del payload non possono essere negativi")
        if self.wem_count + self.bnk_count <= 0:
            raise ValueError("il payload deve contenere almeno un file")
        parsed = urllib.parse.urlsplit(self.url)
        if parsed.scheme.lower() != "https" or not parsed.netloc:
            raise ValueError("l'URL del payload deve usare HTTPS")
        if not self.archive_name or Path(self.archive_name).name != self.archive_name:
            raise ValueError("archive_name deve essere solo un nome di file")

    @property
    def file_count(self) -> int:
        return self.wem_count + self.bnk_count


PRODUCTION_PAYLOAD = PayloadSpec(
    version=PAYLOAD_VERSION,
    archive_name=PAYLOAD_ARCHIVE_NAME,
    url=PAYLOAD_URL,
    archive_size=PAYLOAD_ARCHIVE_SIZE,
    sha256=PAYLOAD_SHA256,
    wem_count=PAYLOAD_WEM_COUNT,
    bnk_count=PAYLOAD_BNK_COUNT,
    uncompressed_size=PAYLOAD_UNCOMPRESSED_SIZE,
    max_file_size=PAYLOAD_MAX_FILE_SIZE,
    tree_sha256=PAYLOAD_TREE_SHA256,
)


@dataclass(frozen=True, slots=True)
class PayloadStats:
    wem_count: int
    bnk_count: int
    total_size: int
    max_file_size: int

    @property
    def file_count(self) -> int:
        return self.wem_count + self.bnk_count


@dataclass(frozen=True, slots=True)
class _ArchiveEntry:
    info: zipfile.ZipInfo
    relative_path: PurePosixPath


def _log(callback: LogCallback | None, message: str) -> None:
    if callback is not None:
        callback(message)


def _progress(callback: ProgressCallback | None, current: int, total: int) -> None:
    if callback is not None:
        callback(current, total)


def _sha256_file(path: Path, progress: ProgressCallback | None = None) -> str:
    digest = hashlib.sha256()
    total = path.stat().st_size
    processed = 0
    _progress(progress, 0, total)
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(DOWNLOAD_CHUNK_SIZE)
            if not chunk:
                break
            digest.update(chunk)
            processed += len(chunk)
            _progress(progress, processed, total)
    return digest.hexdigest()


def _validate_stats(stats: PayloadStats, spec: PayloadSpec, source: Path) -> None:
    errors: list[str] = []
    if stats.wem_count != spec.wem_count:
        errors.append(f"WEM: atteso {spec.wem_count}, trovato {stats.wem_count}")
    if stats.bnk_count != spec.bnk_count:
        errors.append(f"BNK: atteso {spec.bnk_count}, trovato {stats.bnk_count}")
    if stats.file_count != spec.file_count:
        errors.append(
            f"file: attesi {spec.file_count}, trovati {stats.file_count}"
        )
    if stats.total_size != spec.uncompressed_size:
        errors.append(
            f"dimensione decompressa: attesa {spec.uncompressed_size}, "
            f"trovata {stats.total_size}"
        )
    if stats.max_file_size != spec.max_file_size:
        errors.append(
            f"file più grande: atteso {spec.max_file_size}, trovato {stats.max_file_size}"
        )
    if errors:
        raise PayloadValidationError(
            f"Payload non valido in '{source}': " + "; ".join(errors)
        )


def _validate_relative_name(name: str, *, directory: bool = False) -> PurePosixPath:
    if not name or "\x00" in name:
        raise PayloadValidationError("Lo ZIP contiene un nome di file vuoto o con NUL")
    if "\\" in name:
        raise PayloadValidationError(
            f"Lo ZIP contiene un percorso con barra invertita: {name!r}"
        )
    if ":" in name:
        raise PayloadValidationError(
            f"Lo ZIP contiene un percorso con due punti/drive: {name!r}"
        )
    if name.startswith("/") or name.startswith("//"):
        raise PayloadValidationError(f"Lo ZIP contiene un percorso assoluto: {name!r}")

    raw = name[:-1] if directory and name.endswith("/") else name
    parts = raw.split("/")
    if not raw or any(part in ("", ".", "..") for part in parts):
        raise PayloadValidationError(f"Lo ZIP contiene un percorso non sicuro: {name!r}")
    path = PurePosixPath(*parts)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        raise PayloadValidationError(f"Lo ZIP tenta di uscire dalla cartella di destinazione: {name!r}")
    return path


def _zip_entry_kind(info: zipfile.ZipInfo) -> str:
    """Return ``file`` or ``directory`` and reject links/special entries."""

    unix_mode = (info.external_attr >> 16) & 0xFFFF
    file_type = stat.S_IFMT(unix_mode)
    if file_type == stat.S_IFLNK:
        raise PayloadValidationError(f"Lo ZIP contiene un link simbolico: {info.filename!r}")
    if info.is_dir():
        if file_type not in (0, stat.S_IFDIR):
            raise PayloadValidationError(f"Voce speciale nello ZIP: {info.filename!r}")
        return "directory"
    if file_type not in (0, stat.S_IFREG):
        raise PayloadValidationError(f"Voce speciale nello ZIP: {info.filename!r}")
    return "file"


def _payload_extension(path: PurePosixPath) -> str:
    extension = path.suffix.lower()
    if extension not in (".wem", ".bnk"):
        raise PayloadValidationError(
            f"Estensione inattesa nel payload: {path.as_posix()!r}; sono accettati solo .wem e .bnk"
        )
    return extension


def _inspect_zip(
    zf: zipfile.ZipFile, spec: PayloadSpec, source: Path
) -> list[_ArchiveEntry]:
    raw_files: list[tuple[zipfile.ZipInfo, PurePosixPath]] = []
    seen_archive_names: set[str] = set()

    for info in zf.infolist():
        if info.flag_bits & 0x1:
            raise PayloadValidationError(
                f"Lo ZIP contiene un file crittografato: {info.filename!r}"
            )
        if info.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):
            raise PayloadValidationError(
                f"Metodo di compressione non consentito in {info.filename!r}: {info.compress_type}"
            )
        kind = _zip_entry_kind(info)
        path = _validate_relative_name(info.filename, directory=(kind == "directory"))
        canonical = path.as_posix().casefold()
        if canonical in seen_archive_names:
            raise PayloadValidationError(f"Nome duplicato nello ZIP: {info.filename!r}")
        seen_archive_names.add(canonical)
        if kind == "file":
            raw_files.append((info, path))

    if not raw_files:
        raise PayloadValidationError(f"Lo ZIP '{source}' non contiene file")

    # Both historical layouts are accepted: files at archive root or under one
    # literal ``patch_data/`` wrapper.  No arbitrary top-level folder is stripped.
    strip_wrapper = all(
        len(path.parts) > 1 and path.parts[0].casefold() == "patch_data"
        for _, path in raw_files
    )

    entries: list[_ArchiveEntry] = []
    seen_targets: set[str] = set()
    wem_count = 0
    bnk_count = 0
    total_size = 0
    max_file_size = 0
    for info, original_path in raw_files:
        target_path = (
            PurePosixPath(*original_path.parts[1:]) if strip_wrapper else original_path
        )
        extension = _payload_extension(target_path)
        canonical = target_path.as_posix().casefold()
        if canonical in seen_targets:
            raise PayloadValidationError(
                f"Due file dello ZIP puntano alla stessa destinazione: {target_path.as_posix()!r}"
            )
        # A file cannot also be the parent directory of another file.  This
        # matters on platforms where extraction order could otherwise change the
        # outcome.
        parts = target_path.parts
        parent_keys = {
            PurePosixPath(*parts[:index]).as_posix().casefold()
            for index in range(1, len(parts))
        }
        if seen_targets.intersection(parent_keys):
            raise PayloadValidationError(
                f"Conflitto tra file e cartella nello ZIP: {target_path.as_posix()!r}"
            )
        if any(existing.startswith(canonical + "/") for existing in seen_targets):
            raise PayloadValidationError(
                f"Conflitto tra file e cartella nello ZIP: {target_path.as_posix()!r}"
            )
        seen_targets.add(canonical)

        if info.file_size < 0 or info.file_size > spec.max_file_size:
            raise PayloadValidationError(
                f"Dimensione fuori limite in {target_path.as_posix()!r}: {info.file_size}"
            )
        if extension == ".wem":
            wem_count += 1
        else:
            bnk_count += 1
        total_size += info.file_size
        max_file_size = max(max_file_size, info.file_size)
        if total_size > spec.uncompressed_size:
            raise PayloadValidationError(
                f"Lo ZIP supera la dimensione decompressa consentita ({spec.uncompressed_size})"
            )
        entries.append(_ArchiveEntry(info=info, relative_path=target_path))

    stats = PayloadStats(wem_count, bnk_count, total_size, max_file_size)
    _validate_stats(stats, spec, source)
    return entries


def validate_archive(
    archive_path: str | os.PathLike[str],
    *,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    progress: ProgressCallback | None = None,
) -> PayloadStats:
    """Verify archive byte identity and its complete, safe ZIP manifest."""

    path = Path(archive_path)
    try:
        metadata = path.lstat()
    except FileNotFoundError as exc:
        raise PayloadValidationError(
            f"File di payload non trovato: '{path}'"
        ) from exc
    except OSError as exc:
        raise PayloadValidationError(
            f"Impossibile ispezionare il payload '{path}': {exc}"
        ) from exc
    if _metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise PayloadValidationError(
            f"File di payload assente o non sicuro (link/reparse non consentito): '{path}'"
        )
    actual_size = metadata.st_size
    if actual_size != spec.archive_size:
        raise PayloadValidationError(
            f"Dimensione errata di '{path}': attesa {spec.archive_size}, trovata {actual_size}"
        )
    actual_sha256 = _sha256_file(path, progress)
    if actual_sha256 != spec.sha256:
        raise PayloadValidationError(
            f"SHA-256 errato di '{path}': atteso {spec.sha256}, trovato {actual_sha256}"
        )
    try:
        with zipfile.ZipFile(path, "r") as zf:
            entries = _inspect_zip(zf, spec, path)
    except PayloadValidationError:
        raise
    except (OSError, zipfile.BadZipFile, NotImplementedError) as exc:
        raise PayloadValidationError(f"ZIP non valido in '{path}': {exc}") from exc
    return _stats_from_entries(entries)


def _stats_from_entries(entries: Iterable[_ArchiveEntry]) -> PayloadStats:
    wem_count = 0
    bnk_count = 0
    total_size = 0
    max_file_size = 0
    for entry in entries:
        if entry.relative_path.suffix.lower() == ".wem":
            wem_count += 1
        else:
            bnk_count += 1
        total_size += entry.info.file_size
        max_file_size = max(max_file_size, entry.info.file_size)
    return PayloadStats(wem_count, bnk_count, total_size, max_file_size)


def _validate_payload_header(path: Path, extension: str) -> None:
    try:
        with path.open("rb") as stream:
            header = stream.read(12)
    except OSError as exc:
        raise PayloadValidationError(f"Impossibile leggere '{path}': {exc}") from exc
    if extension == ".wem":
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise PayloadValidationError(
                f"File WEM senza intestazione RIFF/WAVE valida: '{path}'"
            )
    elif len(header) < 4 or header[:4] != b"BKHD":
        raise PayloadValidationError(f"File BNK senza intestazione BKHD valida: '{path}'")


def _validate_payload_header_bytes(
    header: bytes, extension: str, relative_text: str
) -> None:
    if extension == ".wem":
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise PayloadValidationError(
                f"File WEM senza intestazione RIFF/WAVE valida: '{relative_text}'"
            )
    elif len(header) < 4 or header[:4] != b"BKHD":
        raise PayloadValidationError(
            f"File BNK senza intestazione BKHD valida: '{relative_text}'"
        )


def _validate_marker(path: Path, spec: PayloadSpec) -> None:
    try:
        marker = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PayloadValidationError(
            f"Marcatore di payload non valido in '{path}': {exc}"
        ) from exc
    if not isinstance(marker, dict):
        raise PayloadValidationError(
            f"Marcatore di payload non valido in '{path}': il JSON deve essere un oggetto"
        )
    expected = _marker_data(spec)
    for field, expected_value in expected.items():
        if marker.get(field) != expected_value:
            raise PayloadValidationError(
                f"Marcatore di payload divergente in '{path}' (campo {field!r})"
            )


def validate_patch_directory(
    patch_data_dir: str | os.PathLike[str],
    *,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    progress: ProgressCallback | None = None,
    expected_file_sha256: Mapping[str, str] | None = None,
) -> PayloadStats:
    """Validate an already extracted payload without following any links."""

    root = Path(patch_data_dir)
    try:
        root_metadata = root.lstat()
    except OSError as exc:
        raise PayloadValidationError(
            f"Cartella di payload assente o non sicura: '{root}'"
        ) from exc
    if _metadata_is_link_or_reparse(root_metadata) or not stat.S_ISDIR(
        root_metadata.st_mode
    ):
        raise PayloadValidationError(
            f"Cartella di payload assente o non sicura: '{root}'"
        )
    root_identity = (root_metadata.st_dev, root_metadata.st_ino)

    wem_count = 0
    bnk_count = 0
    total_size = 0
    max_file_size = 0
    visited_files = 0
    marker_path: Path | None = None
    seen_names: set[str] = set()
    payload_files: list[tuple[str, Path, int, str, tuple[int, int]]] = []
    _progress(progress, 0, spec.file_count)

    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        for directory_name in directory_names:
            directory = current / directory_name
            if _is_link_or_reparse(directory):
                raise PayloadValidationError(
                    f"Link/reparse point non consentito: '{directory}'"
                )

        for file_name in file_names:
            path = current / file_name
            metadata = path.lstat()
            if (
                _metadata_is_link_or_reparse(metadata)
                or not stat.S_ISREG(metadata.st_mode)
                or metadata.st_nlink != 1
            ):
                raise PayloadValidationError(
                    f"Link/reparse/hardlink/tipo non consentito: '{path}'"
                )
            try:
                relative = path.relative_to(root)
            except ValueError as exc:
                raise PayloadValidationError(
                    f"File fuori dal payload: '{path}'"
                ) from exc
            relative_text = relative.as_posix()
            if "\\" in relative_text or ":" in relative_text:
                raise PayloadValidationError(
                    f"Percorso non sicuro nel payload: '{relative_text}'"
                )
            canonical = relative_text.casefold()
            if canonical in seen_names:
                raise PayloadValidationError(
                    f"Nome duplicato nel payload: '{relative_text}'"
                )
            seen_names.add(canonical)

            if relative_text == MARKER_FILENAME:
                marker_path = path
                continue
            extension = relative.suffix.lower()
            if extension not in (".wem", ".bnk"):
                raise PayloadValidationError(
                    f"Estensione inattesa nel payload: '{relative_text}'; sono accettati solo .wem e .bnk"
                )
            size = metadata.st_size
            if size > spec.max_file_size:
                raise PayloadValidationError(
                    f"File eccede il limite ({spec.max_file_size}): '{relative_text}' ({size})"
                )
            # Early diagnostic only; the authenticated hashing pass below
            # validates the same header again through an identity-bound handle.
            _validate_payload_header(path, extension)
            if extension == ".wem":
                wem_count += 1
            else:
                bnk_count += 1
            total_size += size
            max_file_size = max(max_file_size, size)
            payload_files.append(
                (
                    relative_text,
                    path,
                    size,
                    extension,
                    (metadata.st_dev, metadata.st_ino),
                )
            )
            visited_files += 1
            if visited_files > spec.file_count or total_size > spec.uncompressed_size:
                raise PayloadValidationError(
                    f"La cartella '{root}' supera il manifesto consentito"
                )
            _progress(progress, visited_files, spec.file_count)

    stats = PayloadStats(wem_count, bnk_count, total_size, max_file_size)
    _validate_stats(stats, spec, root)
    expected_hashes = dict(expected_file_sha256 or {})
    payload_names = {item[0] for item in payload_files}
    if expected_file_sha256 is not None and set(expected_hashes) != payload_names:
        missing = sorted(payload_names - set(expected_hashes))
        extra = sorted(set(expected_hashes) - payload_names)
        raise PayloadValidationError(
            "Il piano non copre esattamente l'albero autenticato del payload: "
            f"mancanti={missing[:5]}, extra={extra[:5]}"
        )

    # The archive SHA authenticates the ZIP.  This second pinned digest
    # authenticates the extracted tree itself, so a same-size edit with a valid
    # RIFF/BKHD header cannot be accepted from either cache or adjacent data.
    tree_digest = hashlib.sha256()
    try:
        for relative_text, path, expected_size, extension, expected_identity in sorted(
            payload_files, key=lambda item: item[0].casefold()
        ):
            before = path.lstat()
            if (
                _metadata_is_link_or_reparse(before)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or (before.st_dev, before.st_ino) != expected_identity
            ):
                raise PayloadValidationError(
                    f"File cambiato prima dell'autenticazione: '{path}'"
                )
            encoded_path = relative_text.encode("utf-8")
            tree_digest.update(struct.pack("<I", len(encoded_path)))
            tree_digest.update(encoded_path)
            tree_digest.update(struct.pack("<Q", expected_size))
            bytes_read = 0
            file_digest = hashlib.sha256()
            header = bytearray()
            with path.open("rb") as stream:
                opened = os.fstat(stream.fileno())
                if (opened.st_dev, opened.st_ino) != expected_identity:
                    raise PayloadValidationError(
                        f"File sostituito durante l'apertura: '{relative_text}'"
                    )
                while chunk := stream.read(DOWNLOAD_CHUNK_SIZE):
                    bytes_read += len(chunk)
                    tree_digest.update(chunk)
                    file_digest.update(chunk)
                    if len(header) < 12:
                        header.extend(chunk[: 12 - len(header)])
                opened_after = os.fstat(stream.fileno())
            current = path.lstat()
            if (
                bytes_read != expected_size
                or current.st_size != expected_size
                or _metadata_is_link_or_reparse(current)
                or not stat.S_ISREG(current.st_mode)
                or opened_after.st_nlink != 1
                or current.st_nlink != 1
                or (opened_after.st_dev, opened_after.st_ino) != expected_identity
                or (current.st_dev, current.st_ino) != expected_identity
            ):
                raise PayloadValidationError(
                    f"File cambiato durante la validazione: '{relative_text}'"
                )
            _validate_payload_header_bytes(bytes(header), extension, relative_text)
            if expected_file_sha256 is not None:
                expected_digest = expected_hashes[relative_text]
                if (
                    not isinstance(expected_digest, str)
                    or not re.fullmatch(r"[0-9a-f]{64}", expected_digest)
                    or file_digest.hexdigest() != expected_digest
                ):
                    raise PayloadValidationError(
                        f"Il piano è stato costruito con byte non autenticati: '{relative_text}'"
                    )
    except PayloadValidationError:
        raise
    except OSError as exc:
        raise PayloadValidationError(
            f"Errore nel calcolo dell'identità crittografica di '{root}': {exc}"
        ) from exc
    actual_tree_digest = tree_digest.hexdigest()
    if actual_tree_digest != spec.tree_sha256:
        raise PayloadValidationError(
            f"SHA-256 dell'albero estratto errato in '{root}': "
            f"atteso {spec.tree_sha256}, ottenuto {actual_tree_digest}"
        )
    final_root = root.lstat()
    if (
        _metadata_is_link_or_reparse(final_root)
        or not stat.S_ISDIR(final_root.st_mode)
        or (final_root.st_dev, final_root.st_ino) != root_identity
    ):
        raise PayloadValidationError(
            f"La radice del payload è cambiata durante la validazione: '{root}'"
        )
    if marker_path is not None:
        _validate_marker(marker_path, spec)
    _progress(progress, spec.file_count, spec.file_count)
    return stats


def _marker_data(spec: PayloadSpec) -> dict[str, int | str]:
    return {
        "schema": MARKER_SCHEMA,
        "payload_version": spec.version,
        "archive_name": spec.archive_name,
        "archive_sha256": spec.sha256,
        "tree_sha256": spec.tree_sha256,
        "archive_size": spec.archive_size,
        "file_count": spec.file_count,
        "wem_count": spec.wem_count,
        "bnk_count": spec.bnk_count,
        "uncompressed_size": spec.uncompressed_size,
        "max_file_size": spec.max_file_size,
    }


def _write_marker(directory: Path, spec: PayloadSpec) -> None:
    marker = directory / MARKER_FILENAME
    partial = directory / f".{MARKER_FILENAME}.{uuid.uuid4().hex}.tmp"
    owned_identity: tuple[int, int] | None = None
    try:
        with partial.open("x", encoding="utf-8", newline="\n") as stream:
            opened = os.fstat(stream.fileno())
            owned_identity = (opened.st_dev, opened.st_ino)
            json.dump(
                _marker_data(spec), stream, ensure_ascii=True, indent=2, sort_keys=True
            )
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        metadata = partial.lstat()
        if (
            _metadata_is_link_or_reparse(metadata)
            or not stat.S_ISREG(metadata.st_mode)
            or metadata.st_nlink != 1
        ):
            raise PayloadExtractionError(
                f"Marcatore temporaneo cambiato o con hardlink: '{partial}'."
            )
        if (metadata.st_dev, metadata.st_ino) != owned_identity:
            raise PayloadExtractionError(
                f"Marcatore temporaneo sostituito: '{partial}'."
            )
        os.replace(partial, marker)
    except FileExistsError as exc:
        raise PayloadExtractionError(
            f"Lo scratch del marcatore esiste già ed è stato preservato: '{partial}'."
        ) from exc
    finally:
        try:
            _remove_owned_regular_file(partial, owned_identity)
        except (OSError, PatchDataError):
            pass


def _remove_path_without_following(path: Path) -> None:
    """Remove only one leaf/empty path; never recurse through a pathname."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return

    if _metadata_is_link_or_reparse(metadata):
        # A Windows junction is a directory reparse point and must be removed
        # with rmdir.  A normal symlink (including one to a directory) is
        # unlinked.  Neither operation traverses the referenced target.
        if stat.S_ISDIR(metadata.st_mode):
            path.rmdir()
        else:
            path.unlink()
        return

    if not stat.S_ISDIR(metadata.st_mode):
        path.unlink()
        return
    # rmdir never traverses children and therefore cannot follow a directory
    # swapped to a junction between inspection and removal.
    path.rmdir()


def _remove_private_file_without_following(path: Path) -> None:
    """Remove one scratch file/link, but preserve unexpected real directories."""

    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if _metadata_is_link_or_reparse(metadata):
        if stat.S_ISDIR(metadata.st_mode):
            path.rmdir()
        else:
            path.unlink()
        return
    if not stat.S_ISREG(metadata.st_mode):
        raise PatchDataError(
            f"Lo scratch atteso è di un tipo inatteso ed è stato preservato: '{path}'."
        )
    path.unlink()


def _remove_owned_regular_file(
    path: Path, expected_identity: tuple[int, int] | None
) -> None:
    """Remove only the exact private file created by this invocation."""

    if expected_identity is None:
        return
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if (
        _metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
        or (metadata.st_dev, metadata.st_ino) != expected_identity
    ):
        return
    path.unlink()


def _regular_file_identity(path: Path, *, label: str) -> tuple[int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PatchDataError(
            f"Impossibile ispezionare {label} '{path}': {exc}"
        ) from exc
    if (
        _metadata_is_link_or_reparse(metadata)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise PatchDataError(f"{label} è cambiato o possiede un hardlink: '{path}'.")
    return metadata.st_dev, metadata.st_ino


def _sha256_owned_regular(path: Path, expected_identity: tuple[int, int]) -> str:
    """Hash through a descriptor bound to one app-created file identity."""

    if _regular_file_identity(path, label="Il file privato") != expected_identity:
        raise PatchDataError(f"Il file privato è stato sostituito: '{path}'.")
    digest = hashlib.sha256()
    try:
        stream = path.open("rb")
    except OSError as exc:
        raise PatchDataError(
            f"Impossibile aprire il file privato: {exc}"
        ) from exc
    try:
        opened = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or (opened.st_dev, opened.st_ino) != expected_identity
        ):
            raise PatchDataError(f"Il file privato è stato sostituito: '{path}'.")
        while chunk := stream.read(DOWNLOAD_CHUNK_SIZE):
            digest.update(chunk)
        opened_after = os.fstat(stream.fileno())
        current = path.lstat()
        if (
            _metadata_is_link_or_reparse(current)
            or not stat.S_ISREG(current.st_mode)
            or opened_after.st_nlink != 1
            or current.st_nlink != 1
            or (opened_after.st_dev, opened_after.st_ino) != expected_identity
            or (current.st_dev, current.st_ino) != expected_identity
        ):
            raise PatchDataError(
                f"Il file privato è cambiato durante l'autenticazione: '{path}'."
            )
        return digest.hexdigest()
    finally:
        stream.close()


def _move_path_without_replace(source: Path, destination: Path) -> None:
    """Atomically move an app-owned path while refusing a racing destination.

    The supported Windows runtime gives ``os.rename`` create-if-absent
    semantics.  This is deliberately different from ``os.replace``: a file
    created by another process after the pre-check must survive.
    """

    if os.path.lexists(destination):
        raise PatchDataError(
            f"La destinazione è riapparsa durante lo scambio ed è stata preservata: '{destination}'."
        )
    try:
        os.rename(source, destination)
    except FileExistsError as exc:
        raise PatchDataError(
            f"La destinazione è riapparsa durante lo scambio ed è stata preservata: '{destination}'."
        ) from exc
    except OSError as exc:
        raise PatchDataError(
            f"Impossibile spostare atomicamente '{source}' in '{destination}': {exc}"
        ) from exc


def _move_owned_regular_without_replace(
    source: Path,
    destination: Path,
    expected_identity: tuple[int, int],
) -> None:
    """Publish only the exact private file created by this invocation."""

    if _regular_file_identity(source, label="Il download privato") != expected_identity:
        raise PatchDataError(f"Il download privato è stato sostituito: '{source}'.")
    _move_path_without_replace(source, destination)
    if (
        _regular_file_identity(destination, label="Il download pubblicato")
        != expected_identity
    ):
        raise PatchDataError(f"Il download pubblicato è stato sostituito: '{destination}'.")


def _directory_identity(path: Path, *, label: str) -> tuple[int, int]:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise PatchDataError(
            f"Impossibile ispezionare {label} '{path}': {exc}"
        ) from exc
    if _metadata_is_link_or_reparse(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise PatchDataError(f"{label} non è una cartella regolare: '{path}'.")
    return metadata.st_dev, metadata.st_ino


def _move_owned_directory_without_replace(
    source: Path,
    destination: Path,
    expected_identity: tuple[int, int],
) -> None:
    if _directory_identity(source, label="L'albero privato") != expected_identity:
        raise PatchDataError(f"L'albero privato è stato sostituito: '{source}'.")
    _move_path_without_replace(source, destination)
    try:
        if (
            _directory_identity(destination, label="L'albero pubblicato")
            != expected_identity
        ):
            raise PatchDataError(f"L'albero pubblicato è stato sostituito: '{destination}'.")
    except Exception:
        if not os.path.lexists(source) and os.path.lexists(destination):
            try:
                _move_path_without_replace(destination, source)
            except Exception:
                pass
        raise


def _replace_directory_atomically(
    staged: Path,
    destination: Path,
    staged_identity: tuple[int, int] | None = None,
) -> Path | None:
    """Swap a staged directory into place and restore the old one on failure."""

    staged_identity = staged_identity or _directory_identity(
        staged, label="L'estrazione preparata"
    )
    previous: Path | None = None
    destination_exists = os.path.lexists(destination)
    if destination_exists:
        previous = destination.with_name(f".{destination.name}.old-{uuid.uuid4().hex}")
        _move_path_without_replace(destination, previous)
    try:
        _move_owned_directory_without_replace(staged, destination, staged_identity)
    except Exception:
        if previous is not None and not os.path.lexists(destination):
            _move_path_without_replace(previous, destination)
        raise
    # A recursive deletion by pathname can be redirected through a racing
    # junction. Keep the prior tree as an explicit quarantine; recovery ignores
    # it only after the new target validates completely.
    return previous


def extract_archive(
    archive_path: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    *,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
) -> Path:
    """Safely extract a validated archive and atomically publish the result."""

    archive = Path(archive_path)
    target = Path(destination)
    _ensure_safe_directory_tree(
        target.parent, label="La cartella di estrazione del payload"
    )
    _log(log, f"Convalida del file di doppiaggio: {archive}")
    validate_archive(archive, spec=spec)

    staged = Path(
        tempfile.mkdtemp(prefix=f".{target.name}.extract-", dir=target.parent)
    )
    staged_identity = _directory_identity(staged, label="L'estrazione preparata")
    completed = False
    try:
        with zipfile.ZipFile(archive, "r") as zf:
            entries = _inspect_zip(zf, spec, archive)
            extracted_size = 0
            _progress(progress, 0, spec.uncompressed_size)
            for entry in entries:
                output = staged.joinpath(*entry.relative_path.parts)
                output.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with zf.open(entry.info, "r") as source, output.open("xb") as sink:
                    while True:
                        chunk = source.read(DOWNLOAD_CHUNK_SIZE)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > entry.info.file_size:
                            raise PayloadExtractionError(
                                f"Il file si è espanso oltre il manifesto: {entry.relative_path.as_posix()}"
                            )
                        sink.write(chunk)
                        extracted_size += len(chunk)
                        _progress(progress, extracted_size, spec.uncompressed_size)
                    sink.flush()
                    os.fsync(sink.fileno())
                if written != entry.info.file_size:
                    raise PayloadExtractionError(
                        f"Dimensione estratta errata in {entry.relative_path.as_posix()}: "
                        f"attesa {entry.info.file_size}, scritta {written}"
                    )

        validate_patch_directory(staged, spec=spec)
        _write_marker(staged, spec)
        # Bind publication to the same directory that was created above; a
        # replacement/junction at the random staging name is never published.
        previous = _replace_directory_atomically(staged, target, staged_identity)
        completed = True
        if previous is not None:
            _log(
                log,
                "L'albero precedente è stato preservato in quarantena; rimuovilo solo "
                f"dopo aver confermato il nuovo payload: {previous}",
            )
        _log(log, f"Dati di doppiaggio estratti e convalidati in: {target}")
        return target
    except (PayloadValidationError, PayloadExtractionError):
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise PayloadExtractionError(f"Errore durante l'estrazione di '{archive}': {exc}") from exc
    finally:
        if not completed and os.path.lexists(staged):
            _log(
                log,
                "Estrazione incompleta preservata per la revisione (nessuna eliminazione "
                f"ricorsiva non sicura è stata tentata): {staged}",
            )


def download_archive(
    destination: str | os.PathLike[str],
    *,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    opener: UrlOpener = urllib.request.urlopen,
    timeout: float = 60.0,
) -> Path:
    """Download to a private unique file and publish without replacing a target."""

    target = Path(destination)
    _ensure_safe_directory_tree(
        target.parent, label="La cartella di download del payload"
    )
    partial = target.with_name(f".{target.name}.download-{uuid.uuid4().hex}.part")
    request = urllib.request.Request(
        spec.url,
        headers={"User-Agent": "ERPT-BR-source-installer/0.9 (+data-only)"},
        method="GET",
    )
    _log(log, f"Scaricamento dei dati fissati da {spec.url}")
    partial_identity: tuple[int, int] | None = None
    try:
        digest = hashlib.sha256()
        downloaded = 0
        _progress(progress, 0, spec.archive_size)
        with opener(request, timeout=timeout) as response:
            final_url = getattr(response, "geturl", lambda: spec.url)()
            if urllib.parse.urlsplit(final_url).scheme.lower() != "https":
                raise PayloadDownloadError(
                    f"Il download è stato reindirizzato verso un URL senza HTTPS: {final_url}"
                )
            status = getattr(response, "status", 200)
            if status != 200:
                raise PayloadDownloadError(f"Il server ha risposto HTTP {status}")
            headers = getattr(response, "headers", {})
            content_length = (
                headers.get("Content-Length") if headers is not None else None
            )
            if content_length is not None:
                try:
                    announced_size = int(content_length)
                except (TypeError, ValueError) as exc:
                    raise PayloadDownloadError(
                        f"Content-Length non valido ricevuto: {content_length!r}"
                    ) from exc
                if announced_size != spec.archive_size:
                    raise PayloadDownloadError(
                        f"Il server ha annunciato {announced_size} byte; attesi {spec.archive_size}"
                    )

            # ``xb`` plus a random name prevents a pre-planted link or hardlink
            # from being followed and truncated when this process is elevated.
            with partial.open("xb") as stream:
                opened = os.fstat(stream.fileno())
                partial_identity = (opened.st_dev, opened.st_ino)
                while True:
                    chunk = response.read(DOWNLOAD_CHUNK_SIZE)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > spec.archive_size:
                        raise PayloadDownloadError(
                            f"Il download ha superato la dimensione fissata di {spec.archive_size} byte"
                        )
                    stream.write(chunk)
                    digest.update(chunk)
                    _progress(progress, downloaded, spec.archive_size)
                stream.flush()
                os.fsync(stream.fileno())

        downloaded_metadata = partial.lstat()
        if (
            _metadata_is_link_or_reparse(downloaded_metadata)
            or not stat.S_ISREG(downloaded_metadata.st_mode)
            or downloaded_metadata.st_nlink != 1
            or (downloaded_metadata.st_dev, downloaded_metadata.st_ino)
            != partial_identity
        ):
            raise PayloadDownloadError(
                "Il file temporaneo di download è cambiato o possiede un hardlink."
            )

        if downloaded != spec.archive_size:
            raise PayloadDownloadError(
                f"Download incompleto: atteso {spec.archive_size}, ricevuto {downloaded} byte"
            )
        actual_digest = digest.hexdigest()
        if actual_digest != spec.sha256:
            raise PayloadDownloadError(
                f"SHA-256 del download divergente: atteso {spec.sha256}, ricevuto {actual_digest}"
            )
        # Re-read the closed file before publishing it.  Besides validating the
        # ZIP structure, this catches any replacement between the streamed hash
        # and publication.
        try:
            validate_archive(partial, spec=spec)
        except PayloadValidationError as exc:
            raise PayloadDownloadError(
                f"Lo ZIP scaricato non ha superato la convalida: {exc}"
            ) from exc
        except (OSError, zipfile.BadZipFile, NotImplementedError) as exc:
            raise PayloadDownloadError(f"Lo ZIP scaricato non è valido: {exc}") from exc

        try:
            if partial_identity is None:
                raise PatchDataError(
                    "L'identità del download privato non è stata acquisita."
                )
            _move_owned_regular_without_replace(partial, target, partial_identity)
            if _sha256_owned_regular(target, partial_identity) != spec.sha256:
                raise PatchDataError(
                    f"Il download pubblicato non corrisponde allo SHA-256 fissato: '{target}'."
                )
        except PatchDataError as exc:
            raise PayloadDownloadError(
                "La destinazione del download è apparsa durante la pubblicazione ed è stata "
                f"preservata. Nessun file esistente è stato sovrascritto: {exc}"
            ) from exc
        _progress(progress, spec.archive_size, spec.archive_size)
        _log(log, f"Download convalidato (SHA-256 {spec.sha256})")
        return target
    except PayloadDownloadError:
        raise
    except Exception as exc:
        raise PayloadDownloadError(
            f"Errore nel download sicuro del payload: {exc}"
        ) from exc
    finally:
        # ``unlink`` removes a link as an entry and never traverses a directory.
        # If an unexpected directory replaced the random scratch path, preserve
        # it rather than recursively deleting unknown contents.
        try:
            _remove_owned_regular_file(partial, partial_identity)
        except (OSError, PatchDataError):
            pass


def _unique_paths(paths: Iterable[Path]) -> Iterable[Path]:
    seen: set[str] = set()
    for path in paths:
        key = os.path.normcase(os.path.abspath(path))
        if key not in seen:
            seen.add(key)
            yield path


def _is_generated_uuid_suffix(value: str) -> bool:
    return len(value) == 32 and all(
        character in "0123456789abcdefABCDEF" for character in value
    )


def _recover_payload_cache_unlocked(
    cache: Path,
    target: Path,
    *,
    spec: PayloadSpec,
    log: LogCallback | None,
) -> None:
    """Recover interrupted directory swaps while the caller holds the cache lock."""

    if target.parent != cache:
        raise PatchDataError(
            "La destinazione di ripristino del payload è fuori dalla cache prevista"
        )

    extract_prefix = f".{target.name}.extract-"
    old_prefix = f".{target.name}.old-"
    download_prefix = f".{spec.archive_name}.download-"
    extract_residues: list[Path] = []
    old_residues: list[Path] = []
    download_residues: list[Path] = []
    malformed_residues: list[Path] = []
    try:
        cache_entries = list(cache.iterdir())
    except OSError as exc:
        raise PatchDataError(
            f"Impossibile ispezionare la cache del payload '{cache}': {exc}"
        ) from exc

    for entry in cache_entries:
        folded_name = entry.name.casefold()
        if folded_name.startswith(extract_prefix.casefold()):
            suffix = entry.name[len(extract_prefix) :]
            if re.fullmatch(r"[a-z0-9_]{8}", suffix):
                extract_residues.append(entry)
            else:
                malformed_residues.append(entry)
        elif folded_name.startswith(old_prefix.casefold()):
            suffix = entry.name[len(old_prefix) :]
            if _is_generated_uuid_suffix(suffix):
                old_residues.append(entry)
            else:
                malformed_residues.append(entry)
        elif folded_name.startswith(download_prefix.casefold()):
            suffix = entry.name[len(download_prefix) :]
            if suffix.casefold().endswith(".part") and _is_generated_uuid_suffix(
                suffix[:-5]
            ):
                download_residues.append(entry)
            else:
                malformed_residues.append(entry)

    # Download residues are single leaf entries, so unlinking them cannot
    # traverse a directory junction. Clean these even when the final tree is valid.
    for residue in sorted(download_residues, key=lambda path: path.name.casefold()):
        try:
            _remove_private_file_without_following(residue)
        except (OSError, PatchDataError) as exc:
            raise PatchDataError(
                f"Impossibile ripulire il download interrotto '{residue}'. "
                "Nessun nuovo payload è stato creato; chiudi le altre istanze e riprova. "
                f"Dettaglio: {exc}"
            ) from exc
        _log(log, f"Download interrotto rimosso in sicurezza: {residue}")

    target_valid = False
    if os.path.lexists(target):
        try:
            validate_patch_directory(target, spec=spec)
            target_valid = True
        except (PayloadValidationError, OSError):
            pass
    if target_valid:
        for residue in sorted(
            extract_residues + old_residues + malformed_residues,
            key=lambda path: path.name.casefold(),
        ):
            _log(
                log,
                "Residuo privato preservato; il payload pubblicato è già stato autenticato: "
                f"{residue}",
            )
        # The exact target will be validated once more by the caller before use.
        return

    # Crash residues have no in-memory ownership identities. Never recursively
    # delete them by pathname: a racing directory junction could redirect such
    # cleanup outside the cache. They are inert and are never selected as data.
    for residue in sorted(extract_residues, key=lambda path: path.name.casefold()):
        _log(log, f"Estrazione interrotta preservata e ignorata: {residue}")

    if malformed_residues:
        names = ", ".join(
            repr(path.name)
            for path in sorted(
                malformed_residues, key=lambda path: path.name.casefold()
            )
        )
        raise PatchDataError(
            "La cache contiene residui di transazione con nomi inattesi "
            f"({names}). Sono stati preservati; controlla manualmente la cache."
        )

    if len(old_residues) > 1:
        names = ", ".join(
            repr(path.name)
            for path in sorted(old_residues, key=lambda path: path.name.casefold())
        )
        raise PatchDataError(
            "La cache contiene più backup di uno scambio interrotto "
            f"({names}). Sono stati tutti preservati perché non è sicuro indovinare quale usare."
        )
    if not old_residues:
        return

    previous = old_residues[0]
    if os.path.lexists(target):
        try:
            validate_patch_directory(target, spec=spec)
        except (PayloadValidationError, OSError) as exc:
            raise PatchDataError(
                "La cache è in uno stato ambiguo: la destinazione attuale non è valida e "
                f"anche il backup '{previous.name}' esiste. Entrambi sono stati preservati. "
                f"Dettaglio sulla destinazione: {exc}"
            ) from exc
        _log(
            log,
            f"Backup precedente preservato in quarantena dopo aver convalidato quello attuale: {previous}",
        )
        return

    previous_identity = _directory_identity(previous, label="Il backup di payload")
    try:
        validate_patch_directory(previous, spec=spec)
    except (PayloadValidationError, OSError) as exc:
        raise PatchDataError(
            "Uno scambio è stato interrotto senza lasciare la destinazione finale, ma l'unico "
            f"backup trovato non è valido ('{previous}'). È stato preservato. "
            f"Dettaglio: {exc}"
        ) from exc

    # Validation selected exactly one complete backup.  Recheck the destination
    # immediately before the same-filesystem atomic rename; never replace bytes
    # that appeared while recovery was running.
    if os.path.lexists(target):
        raise PatchDataError(
            "La destinazione del payload è riapparsa durante il ripristino. Il backup è stato "
            "preservato e nessun file è stato sostituito."
        )
    try:
        _move_owned_directory_without_replace(previous, target, previous_identity)
    except (OSError, PatchDataError) as exc:
        raise PatchDataError(
            f"Impossibile ripristinare atomicamente '{previous}' in '{target}': {exc}"
        ) from exc

    try:
        validate_patch_directory(target, spec=spec)
    except (PayloadValidationError, OSError) as exc:
        rollback_error: OSError | None = None
        try:
            if os.path.lexists(target) and not os.path.lexists(previous):
                _move_path_without_replace(target, previous)
        except (OSError, PatchDataError) as rollback_exc:
            rollback_error = rollback_exc
        detail = f"Errore nella convalida successiva: {exc}"
        if rollback_error is not None:
            detail += f"; errore nel ripristinare il backup: {rollback_error}"
        raise PatchDataError(
            "Il backup è cambiato durante il ripristino. L'operazione è stata interrotta. "
            + detail
        ) from exc
    _log(log, f"Payload ripristinato da uno scambio interrotto: {target}")


def _default_cache_directory() -> Path:
    local_data = os.environ.get("LOCALAPPDATA")
    if local_data:
        return _absolute_without_resolving(Path(local_data) / "ERPT-BR" / "payload")
    return _absolute_without_resolving(
        Path.home() / ".local" / "share" / "ERPT-BR" / "payload"
    )


def _ensure_patch_data_unlocked(
    adjacent_dir: str | os.PathLike[str],
    *,
    cache_dir: str | os.PathLike[str] | None = None,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    opener: UrlOpener = urllib.request.urlopen,
) -> Path:
    """Return a strongly validated ``patch_data`` directory.

    Search order is an extracted adjacent directory, extracted cache, adjacent
    archives, cached archives, and finally a data-only HTTPS download.  Invalid
    candidates are logged and skipped; they are never consumed by the patcher.
    """

    adjacent = Path(adjacent_dir).resolve()
    cache = _ensure_safe_directory_tree(
        cache_dir if cache_dir is not None else _default_cache_directory(),
        label="La cache del payload",
    )
    extracted_target = cache / "patch_data"

    directory_candidates = _unique_paths((adjacent / "patch_data", extracted_target))
    for candidate in directory_candidates:
        if not os.path.lexists(candidate):
            continue
        try:
            _log(log, f"Convalida dei dati locali: {candidate}")
            validate_patch_directory(candidate, spec=spec, progress=progress)
            _log(log, f"Dati locali convalidati: {candidate}")
            return candidate
        except PayloadValidationError as exc:
            _log(log, f"Dati locali ignorati per errore di convalida: {exc}")

    archive_candidates = _unique_paths(
        (
            adjacent / "patch_data.zip",
            adjacent / spec.archive_name,
            cache / spec.archive_name,
            cache / "patch_data.zip",
        )
    )
    for archive in archive_candidates:
        if not archive.is_file():
            continue
        try:
            _log(log, f"Convalida dello ZIP locale: {archive}")
            validate_archive(archive, spec=spec, progress=progress)
            return extract_archive(
                archive,
                extracted_target,
                spec=spec,
                log=log,
                progress=progress,
            )
        except (PayloadValidationError, PayloadExtractionError) as exc:
            _log(log, f"ZIP locale ignorato per errore di convalida: {exc}")

    downloaded_archive = cache / spec.archive_name
    if os.path.lexists(downloaded_archive):
        try:
            metadata = downloaded_archive.lstat()
        except OSError as exc:
            raise PatchDataError(
                f"Lo ZIP non valido della cache non può essere ispezionato: {exc}"
            ) from exc
        if _metadata_is_link_or_reparse(metadata) or not stat.S_ISREG(metadata.st_mode):
            raise PatchDataError(
                "Il percorso riservato allo ZIP della cache contiene un link, reparse point "
                f"o tipo inatteso ed è stato preservato: '{downloaded_archive}'."
            )
        try:
            downloaded_archive.unlink()
        except OSError as exc:
            raise PatchDataError(
                f"Lo ZIP non valido della cache non può essere rimosso in sicurezza: {exc}"
            ) from exc
        _log(log, f"ZIP non valido rimosso dalla cache: {downloaded_archive}")
    download_archive(
        downloaded_archive,
        spec=spec,
        log=log,
        progress=progress,
        opener=opener,
    )
    try:
        return extract_archive(
            downloaded_archive,
            extracted_target,
            spec=spec,
            log=log,
            progress=progress,
        )
    except (PayloadValidationError, PayloadExtractionError):
        # A successfully downloaded archive is retained for diagnostics and for
        # a later retry; it remains cryptographically verified data.
        raise


def ensure_patch_data(
    adjacent_dir: str | os.PathLike[str],
    *,
    cache_dir: str | os.PathLike[str] | None = None,
    spec: PayloadSpec = PRODUCTION_PAYLOAD,
    log: LogCallback | None = None,
    progress: ProgressCallback | None = None,
    opener: UrlOpener = urllib.request.urlopen,
) -> Path:
    """Return authenticated audio data while serializing cache writers."""
    cache = _ensure_safe_directory_tree(
        cache_dir if cache_dir is not None else _default_cache_directory(),
        label="La cache del payload",
    )
    with PayloadCacheLock(cache / ".payload.lock"):
        _recover_payload_cache_unlocked(
            cache,
            cache / "patch_data",
            spec=spec,
            log=log,
        )
        return _ensure_patch_data_unlocked(
            adjacent_dir,
            cache_dir=cache,
            spec=spec,
            log=log,
            progress=progress,
            opener=opener,
        )


__all__ = [
    "MARKER_FILENAME",
    "PAYLOAD_ARCHIVE_NAME",
    "PAYLOAD_ARCHIVE_SIZE",
    "PAYLOAD_BNK_COUNT",
    "PAYLOAD_FILE_COUNT",
    "PAYLOAD_MAX_FILE_SIZE",
    "PAYLOAD_SHA256",
    "PAYLOAD_TREE_SHA256",
    "PAYLOAD_UNCOMPRESSED_SIZE",
    "PAYLOAD_URL",
    "PAYLOAD_VERSION",
    "PAYLOAD_WEM_COUNT",
    "PRODUCTION_PAYLOAD",
    "PatchDataError",
    "PayloadDownloadError",
    "PayloadExtractionError",
    "PayloadCacheLock",
    "PayloadSpec",
    "PayloadStats",
    "PayloadValidationError",
    "download_archive",
    "ensure_patch_data",
    "extract_archive",
    "validate_archive",
    "validate_patch_directory",
]
