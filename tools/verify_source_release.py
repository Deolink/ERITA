#!/usr/bin/env python3
"""Valida de forma independente a allowlist do release source-only."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import os
import re
import stat
import zipfile
import zlib
from pathlib import Path, PurePosixPath


SOURCE_FILES = frozenset(
    {
        "ERPT-BR.cmd",
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
EXPECTED_FILES = SOURCE_FILES | frozenset(WHEEL_SHA256)
FORBIDDEN_SUFFIXES = {".exe", ".dll", ".bat", ".ps1", ".scr", ".com"}
MAX_MEMBER_SIZE = 5 * 1024 * 1024
MAX_TOTAL_UNCOMPRESSED = 8 * 1024 * 1024
MAX_TOTAL_COMPRESSED = 8 * 1024 * 1024
MAX_ARCHIVE_SIZE = 8 * 1024 * 1024
FORBIDDEN_SOURCE_PATTERNS = {
    "exec(compile(": "execucao dinamica de codigo",
    "taskkill": "encerramento forcado de processos",
    "shellexecutew": "auto-elevacao UAC",
    "pyinstaller": "empacotador executavel",
    "nuitka": "empacotador executavel",
    "invoke-expression": "execucao dinamica do PowerShell",
    "-encodedcommand": "comando PowerShell codificado",
    "-executionpolicy bypass": "contorno da politica do PowerShell",
    "--ignore-security-hash": "contorno do hash de seguranca do WinGet",
    "installallusers=1": "instalacao global com elevacao",
    "-verb runas": "auto-elevacao UAC",
    "http://": "download sem HTTPS",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify(path: str) -> None:
    archive_path = Path(path)
    try:
        metadata = archive_path.lstat()
    except OSError as exc:
        raise SystemExit(f"Release ausente ou ilegivel: {archive_path}") from exc
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    file_attributes = getattr(metadata, "st_file_attributes", 0)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or bool(reparse_flag and file_attributes & reparse_flag)
    ):
        raise SystemExit("O release precisa ser um arquivo regular, nao um link.")
    if metadata.st_size > MAX_ARCHIVE_SIZE:
        raise SystemExit("O arquivo ZIP excede o limite fisico do release.")

    with contextlib.ExitStack() as stack:
        try:
            archive_stream = stack.enter_context(archive_path.open("rb"))
        except OSError as exc:
            raise SystemExit(f"Release ausente ou ilegivel: {archive_path}") from exc
        opened = os.fstat(archive_stream.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_size > MAX_ARCHIVE_SIZE
            or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino)
        ):
            raise SystemExit("O release mudou ou excede o limite antes da leitura.")
        archive = stack.enter_context(zipfile.ZipFile(archive_stream, "r"))
        infos = archive.infolist()
        if len(infos) != len(EXPECTED_FILES):
            raise SystemExit("O ZIP contem uma quantidade inesperada de membros.")
        names = [info.filename for info in infos]
        if not names or len(names) != len(set(names)):
            raise SystemExit("O ZIP esta vazio ou contem nomes duplicados.")
        if len(names) != len({name.casefold() for name in names}):
            raise SystemExit("O ZIP contem nomes duplicados por diferenca de caixa.")

        roots: set[str] = set()
        relative_names: set[str] = set()
        relative_casefolds: set[str] = set()
        members: dict[str, zipfile.ZipInfo] = {}
        total_uncompressed = 0
        total_compressed = 0
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
                raise SystemExit(f"Caminho inseguro no release: {name}")
            roots.add(pure.parts[0])
            relative = PurePosixPath(*pure.parts[1:]).as_posix()
            folded_relative = relative.casefold()
            if folded_relative in relative_casefolds:
                raise SystemExit(f"Destino relativo duplicado no release: {relative}")
            relative_names.add(relative)
            relative_casefolds.add(folded_relative)
            members[relative] = info

            if info.flag_bits & 0x1:
                raise SystemExit(f"Membro criptografado proibido no release: {name}")
            if info.compress_type not in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}:
                raise SystemExit(f"Compressao inesperada no release: {name}")
            if info.file_size > MAX_MEMBER_SIZE or info.compress_size > MAX_MEMBER_SIZE:
                raise SystemExit(f"Membro grande demais no release: {name}")
            total_uncompressed += info.file_size
            total_compressed += info.compress_size
            if (
                total_uncompressed > MAX_TOTAL_UNCOMPRESSED
                or total_compressed > MAX_TOTAL_COMPRESSED
            ):
                raise SystemExit("O tamanho total declarado do release excede o limite.")
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            file_type = stat.S_IFMT(unix_mode)
            if info.is_dir() or file_type not in (0, stat.S_IFREG):
                raise SystemExit(f"Link/diretorio/arquivo especial proibido: {name}")
            if pure.suffix.casefold() in FORBIDDEN_SUFFIXES:
                raise SystemExit(f"Binario/script proibido no release: {name}")

        if len(roots) != 1:
            raise SystemExit("O ZIP precisa ter uma unica pasta raiz.")
        root = next(iter(roots))
        match = re.fullmatch(r"ERPT-BR-v(\d+\.\d+\.\d+)", root)
        if not match:
            raise SystemExit(f"Pasta raiz inesperada no release: {root!r}")
        if relative_names != EXPECTED_FILES:
            missing = sorted(EXPECTED_FILES - relative_names)
            extra = sorted(relative_names - EXPECTED_FILES)
            raise SystemExit(
                f"Allowlist do release divergente; ausentes={missing}, extras={extra}"
            )
        root_commands = sorted(
            relative
            for relative in relative_names
            if "/" not in relative
            and PurePosixPath(relative).suffix.casefold() == ".cmd"
        )
        if root_commands != ["ERPT-BR.cmd"]:
            raise SystemExit(
                "O release precisa expor somente ERPT-BR.cmd na pasta principal."
            )

        # Force decompression and CRC validation for every allowlisted member,
        # including documentation and the icon.  Keeping the bytes also avoids
        # parsing a different view if the archive is replaced during validation.
        try:
            member_bytes = {
                relative: archive.read(info) for relative, info in members.items()
            }
        except (OSError, EOFError, RuntimeError, zipfile.BadZipFile, zlib.error) as exc:
            raise SystemExit(
                "Falha de integridade, descompressao ou CRC em membro do release."
            ) from exc

        for relative in SOURCE_FILES:
            if PurePosixPath(relative).suffix.casefold() not in {".py", ".cmd"}:
                continue
            try:
                source = member_bytes[relative].decode("utf-8")
            except UnicodeDecodeError as exc:
                raise SystemExit(f"Fonte nao UTF-8 no release: {relative}") from exc
            folded_source = source.casefold()
            for pattern, label in FORBIDDEN_SOURCE_PATTERNS.items():
                if pattern in folded_source:
                    raise SystemExit(f"{label} encontrado em {relative}: {pattern}")

        for relative, expected in WHEEL_SHA256.items():
            actual = _sha256(member_bytes[relative])
            if actual != expected:
                raise SystemExit(
                    f"SHA-256 incorreto para {relative}: esperado {expected}, obtido {actual}"
                )

        one_click = member_bytes["ERPT-BR.cmd"].decode("utf-8")
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
                f"Controles obrigatorios ausentes do instalador: {missing_controls}"
            )
        if 'Scripts\\pythonw.exe" -I -S -c' not in launcher:
            raise SystemExit(
                "O launcher nao inicia o Python sem processamento automatico de site."
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
                "O launcher nao valida a compatibilidade do Python e do venv."
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
            "Local\\ERPTBR_Installer_",
            'set "ERPTBR_INTERNAL_CALL=1"',
            ":invalid_package",
        )
        missing_one_click = [
            item for item in required_one_click_controls if item not in one_click
        ]
        if missing_one_click:
            raise SystemExit(
                "Controles obrigatorios ausentes da instalacao de um clique: "
                f"{missing_one_click}"
            )
        if one_click.count("goto :install_direct") != 1:
            raise SystemExit(
                "O fallback direto so pode ser alcancado quando o WinGet esta ausente."
            )
        for relative, expected in WHEEL_SHA256.items():
            bootstrap_relative = relative.replace("/", "\\")
            if bootstrap_relative not in one_click or expected not in one_click:
                raise SystemExit(
                    f"Preflight do bootstrap nao fixa nome/hash de {relative}."
                )
        preflight_order = (
            one_click.find("rem Recusa ZIP automatico"),
            one_click.find("call :find_python"),
            one_click.find('"%ERPT_WINGET%" install'),
        )
        if not (
            -1 not in preflight_order
            and preflight_order[0] < preflight_order[1] < preflight_order[2]
        ):
            raise SystemExit(
                "O pacote precisa ser autenticado antes de instalar o Python."
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
                "Hash e assinatura precisam anteceder a execucao do instalador oficial."
            )

        version = match.group(1)
        init_source = member_bytes["patcher/__init__.py"].decode("utf-8")
        gui_source = member_bytes["patcher/patcher_gui.py"].decode("utf-8")
        if f'__version__ = "{version}"' not in init_source or (
            f'PATCHER_VERSION = "{version}"' not in gui_source
        ):
            raise SystemExit("Versao da pasta raiz diverge do codigo empacotado.")
        lock_source = member_bytes["patcher/requirements-win64.lock"].decode("utf-8")
        for expected in WHEEL_SHA256.values():
            if f"--hash=sha256:{expected}" not in lock_source:
                raise SystemExit(
                    f"Hash de wheel ausente do requirements-win64.lock: {expected}"
                )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive")
    args = parser.parse_args()
    verify(args.archive)
    print("Release source verificado por allowlist e hashes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
