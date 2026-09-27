from __future__ import annotations

import gzip
import hashlib
import io
import struct
import tarfile
import tempfile
import unittest
import zipfile
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from tools import build_linux_release, verify_linux_release


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _tree_sha(files: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    for relative, data in files:
        encoded = relative.encode("utf-8")
        digest.update(struct.pack("<I", len(encoded)))
        digest.update(encoded)
        digest.update(struct.pack("<Q", len(data)))
        digest.update(data)
    return digest.hexdigest()


def _small_payload(path: Path) -> tuple[bytes, list[tuple[str, bytes]]]:
    files = [
        ("a.wem", b"RIFF\x08\x00\x00\x00WAVEdata"),
        ("b.bnk", b"BKHDok"),
    ]
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative, data in files:
            archive.writestr(f"patch_data/{relative}", data)
    payload = stream.getvalue()
    path.write_bytes(payload)
    return payload, files


def _payload_overrides(
    payload: bytes, files: list[tuple[str, bytes]]
) -> dict[str, int | str]:
    return {
        "PAYLOAD_ARCHIVE_SIZE": len(payload),
        "PAYLOAD_SHA256": hashlib.sha256(payload).hexdigest(),
        "PAYLOAD_TREE_SHA256": _tree_sha(files),
        "PAYLOAD_FILE_COUNT": len(files),
        "PAYLOAD_WEM_COUNT": 1,
        "PAYLOAD_BNK_COUNT": 1,
        "PAYLOAD_UNCOMPRESSED_SIZE": sum(len(data) for _name, data in files),
        "PAYLOAD_MAX_FILE_SIZE": max(len(data) for _name, data in files),
    }


def _add_runtime_regular(
    archive: tarfile.TarFile, name: str, data: bytes, mode: int = 0o644
) -> None:
    info = tarfile.TarInfo(name)
    info.type = tarfile.REGTYPE
    info.mode = mode
    info.size = len(data)
    archive.addfile(info, io.BytesIO(data))


def _small_runtime(path: Path, *, escaping_link: bool = False) -> bytes:
    stream = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=stream, mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
            _add_runtime_regular(
                archive, "python/bin/python3.13", b"python", mode=0o755
            )
            _add_runtime_regular(archive, "python/lib/libtcl9.0.so", b"tcl")
            _add_runtime_regular(archive, "python/lib/libtcl9tk9.0.so", b"tk")
            _add_runtime_regular(
                archive,
                "python/lib/python3.13/lib-dynload/_tkinter.fixture.so",
                b"tkinter",
            )
            # Linux permits these distinct terminfo names.
            _add_runtime_regular(archive, "python/share/terminfo/2/2621A", b"A")
            _add_runtime_regular(archive, "python/share/terminfo/2/2621a", b"a")
            link = tarfile.TarInfo("python/bin/python3")
            link.type = tarfile.SYMTYPE
            link.mode = 0o777
            link.linkname = "python3.13"
            archive.addfile(link)
            relative_link = tarfile.TarInfo("python/share/terminfo/2/alias")
            relative_link.type = tarfile.SYMTYPE
            relative_link.mode = 0o777
            relative_link.linkname = (
                "../../../../../outside" if escaping_link else "../../target"
            )
            archive.addfile(relative_link)
    result = stream.getvalue()
    path.write_bytes(result)
    return result


def _fixture_wheels(wheelhouse: Path) -> dict[str, tuple[int, str]]:
    wheelhouse.mkdir()
    result: dict[str, tuple[int, str]] = {}
    for index, name in enumerate(build_linux_release.WHEELS, start=1):
        data = f"fixture-wheel-{index}-{name}".encode("utf-8")
        (wheelhouse / name).write_bytes(data)
        result[name] = (len(data), hashlib.sha256(data).hexdigest())
    return result


def _fixture_root(
    root: Path,
    runtime_bytes: bytes,
    wheels: dict[str, tuple[int, str]],
) -> None:
    old_runtime_size = str(build_linux_release.RUNTIME_ARCHIVE_SIZE)
    old_runtime_hash = build_linux_release.RUNTIME_SHA256
    new_runtime_size = str(len(runtime_bytes))
    new_runtime_hash = hashlib.sha256(runtime_bytes).hexdigest()
    wheel_replacements = {
        original_hash: wheels[name][1]
        for name, (_size, original_hash) in build_linux_release.WHEELS.items()
    }
    for relative in build_linux_release.SOURCE_FILES:
        source = REPOSITORY_ROOT / relative
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        if relative == "interno/INICIAR_LINUX.sh":
            text = data.decode("utf-8")
            text = text.replace(old_runtime_size, new_runtime_size)
            text = text.replace(old_runtime_hash, new_runtime_hash)
            for old, new in wheel_replacements.items():
                text = text.replace(old, new)
            data = text.encode("utf-8")
        elif relative == "patcher/requirements-linux-x86_64.lock":
            text = data.decode("utf-8")
            for old, new in wheel_replacements.items():
                text = text.replace(old, new)
            data = text.encode("utf-8")
        target.write_bytes(data)


def _patch_modules(
    payload_overrides: dict[str, int | str],
    runtime_bytes: bytes,
    wheels: dict[str, tuple[int, str]],
) -> ExitStack:
    stack = ExitStack()
    runtime_overrides = {
        "RUNTIME_ARCHIVE_SIZE": len(runtime_bytes),
        "RUNTIME_SHA256": hashlib.sha256(runtime_bytes).hexdigest(),
    }
    stack.enter_context(
        mock.patch.multiple(
            build_linux_release,
            WHEELS=wheels,
            **runtime_overrides,
            **payload_overrides,
        )
    )
    verifier_wheels = {f"wheelhouse/{name}": value for name, value in wheels.items()}
    verifier_payload = dict(payload_overrides)
    verifier_payload.pop("PAYLOAD_ARCHIVE_SIZE")
    verifier_payload.pop("PAYLOAD_SHA256")
    stack.enter_context(
        mock.patch.multiple(
            verify_linux_release,
            WHEELS=verifier_wheels,
            **runtime_overrides,
            **verifier_payload,
        )
    )
    return stack


class LinuxReleaseTests(unittest.TestCase):
    def test_sellen_vanilla_guard_rejects_every_numeric_wem_alias(self) -> None:
        aliases = (
            "enus/wem/55/553755359.wem",
            "553755359.wem",
            "wem/55/553755359.WEM",
            "foo/553755359.wem",
        )
        for relative in aliases:
            with self.subTest(relative=relative):
                self.assertTrue(build_linux_release._is_sellen_vanilla_wem(relative))
                self.assertTrue(verify_linux_release._is_sellen_vanilla_wem(relative))
        self.assertFalse(
            build_linux_release._is_sellen_vanilla_wem("553755359.bnk")
        )
        self.assertFalse(
            verify_linux_release._is_sellen_vanilla_wem("553755360.wem")
        )

    def test_final_constants_pin_linux_portable_release(self) -> None:
        self.assertEqual(build_linux_release.FINAL_VERSION, "v0.9.7")
        self.assertEqual(
            build_linux_release.FINAL_ARCHIVE_NAME,
            "ERPT-BR-v0.9.7-Linux-x86_64.tar.gz",
        )
        self.assertEqual(build_linux_release.RUNTIME_ARCHIVE_SIZE, 34_993_852)
        self.assertEqual(
            build_linux_release.RUNTIME_SHA256,
            "d0b640eed27fbdd6f5f2bd33444aee53df2c8863f8b2a96f4094717411e3de9c",
        )
        self.assertEqual(
            build_linux_release.PAYLOAD_TREE_SHA256,
            verify_linux_release.PAYLOAD_TREE_SHA256,
        )
        self.assertNotIn("patcher/requirements-win64.lock", build_linux_release.SOURCE_FILES)
        self.assertFalse(any(name.casefold().endswith(".cmd") for name in build_linux_release.SOURCE_FILES))

    def test_runtime_accepts_case_distinct_names_and_safe_parent_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / build_linux_release.RUNTIME_ARCHIVE_NAME
            data = _small_runtime(runtime)
            overrides = {
                "RUNTIME_ARCHIVE_SIZE": len(data),
                "RUNTIME_SHA256": hashlib.sha256(data).hexdigest(),
            }
            with mock.patch.multiple(build_linux_release, **overrides):
                build_linux_release.validate_runtime(runtime)
            with runtime.open("rb") as stream:
                verify_linux_release._validate_runtime_tar(stream)

    def test_runtime_rejects_symlink_that_escapes_python(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime.tar.gz"
            _small_runtime(runtime, escaping_link=True)
            with runtime.open("rb") as stream:
                with self.assertRaisesRegex(SystemExit, "escapa de python"):
                    build_linux_release._validate_runtime_tar(stream)
            with runtime.open("rb") as stream:
                with self.assertRaisesRegex(SystemExit, "escapa de python"):
                    verify_linux_release._validate_runtime_tar(stream)

    def test_builder_is_deterministic_and_independent_verifier_accepts_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "root"
            wheelhouse = base / "wheelhouse"
            payload_path = base / "payload.zip"
            runtime_path = base / build_linux_release.RUNTIME_ARCHIVE_NAME
            payload, files = _small_payload(payload_path)
            runtime = _small_runtime(runtime_path)
            wheels = _fixture_wheels(wheelhouse)
            _fixture_root(root, runtime, wheels)
            overrides = _payload_overrides(payload, files)
            first = base / "one" / build_linux_release.FINAL_ARCHIVE_NAME
            second = base / "two" / build_linux_release.FINAL_ARCHIVE_NAME

            with _patch_modules(overrides, runtime, wheels):
                build_linux_release.build(
                    root,
                    wheelhouse,
                    payload_path,
                    runtime_path,
                    first,
                    build_linux_release.FINAL_VERSION,
                )
                build_linux_release.build(
                    root,
                    wheelhouse,
                    payload_path,
                    runtime_path,
                    second,
                    build_linux_release.FINAL_VERSION,
                )
                self.assertEqual(first.read_bytes(), second.read_bytes())
                verify_linux_release.verify(first)

            with tarfile.open(first, "r:gz") as archive:
                infos = archive.getmembers()
            files_started = False
            for info in infos:
                if info.isfile():
                    files_started = True
                    relative = info.name.removeprefix(
                        f"{build_linux_release.FINAL_PACKAGE_ROOT}/"
                    )
                    self.assertEqual(
                        info.mode,
                        0o755
                        if relative in build_linux_release.EXECUTABLE_FILES
                        else 0o644,
                    )
                else:
                    self.assertFalse(files_started, info.name)
                    self.assertTrue(info.isdir())
                    self.assertEqual(info.mode, 0o755)
                self.assertFalse(
                    info.name.casefold().endswith((".cmd", ".exe", ".dll", ".pyd"))
                )

    def test_verifier_rejects_outer_symlink_member(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / verify_linux_release.FINAL_ARCHIVE_NAME
            with archive_path.open("wb") as raw:
                with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as zipped:
                    with tarfile.open(
                        fileobj=zipped, mode="w|", format=tarfile.USTAR_FORMAT
                    ) as archive:
                        root = tarfile.TarInfo(verify_linux_release.FINAL_PACKAGE_ROOT)
                        root.type = tarfile.DIRTYPE
                        root.mode = 0o755
                        root.uid = root.gid = 0
                        root.mtime = verify_linux_release.ARCHIVE_MTIME
                        archive.addfile(root)
                        link = tarfile.TarInfo(
                            f"{verify_linux_release.FINAL_PACKAGE_ROOT}/ERPT-BR.sh"
                        )
                        link.type = tarfile.SYMTYPE
                        link.mode = 0o755
                        link.uid = link.gid = 0
                        link.mtime = verify_linux_release.ARCHIVE_MTIME
                        link.linkname = "/bin/sh"
                        archive.addfile(link)
            with self.assertRaisesRegex(SystemExit, "Tipo de membro proibido"):
                verify_linux_release.verify(archive_path)


if __name__ == "__main__":
    unittest.main()
