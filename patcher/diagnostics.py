"""Diagnosticos locais e opt-in para o instalador ERPT-BR.

O relatorio usa uma lista fechada de campos. Ele nunca envia dados,
nao consulta variaveis de ambiente e nao inclui o caminho escolhido pelo
usuario. O chamador decide se o texto sera copiado, salvo ou compartilhado.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import re
from typing import Iterable
import uuid


REPORT_SCHEMA = "erptbr-diagnostic"
REPORT_SCHEMA_VERSION = 1
MAX_ERROR_MESSAGE_CHARS = 1_200
MAX_LOG_LINES = 80
MAX_LOG_LINE_CHARS = 500
MAX_LOG_TOTAL_CHARS = 8_000
MAX_GENERIC_FIELD_CHARS = 256
MAX_REPORT_BYTES = 32 * 1024
_MAX_SANITIZER_INPUT_CHARS = 65_536
_CONTROL_CHARACTER_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL_RE = re.compile(
    r"(?<![\w@])[\w.!#$%&'*+/=?^`{|}~-]+@[^\s@]+",
    re.IGNORECASE,
)
_STEAM_ID_RE = re.compile(
    r"(?<!\w)(?:7656119\d{10}|STEAM_[0-5]:[01]:\d+|\[U:1:\d+\])(?!\w)",
    re.IGNORECASE,
)
_STEAM_ID_ASSIGNMENT_RE = re.compile(
    r"(?i)(?<![a-z0-9_])[\"']?steam[ _.-]?id[\"']?\s*[:=]\s*[^\r\n]*"
)
_URL_RE = re.compile(r"(?i)\b[a-z][a-z0-9+.-]*://[^\s\r\n]*")
_KNOWN_TOKEN_RE = re.compile(
    r"(?i)\b(?:github_pat_[A-Za-z0-9_]{12,}|gh[pousr]_[A-Za-z0-9]{12,}|"
    r"sk-[A-Za-z0-9_-]{16,})\b"
)
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(?<![a-z0-9_])[\"']?("
    r"[a-z0-9_.\[\]-]*(?:secret|token|password|passwd|passphrase|credential|cookie|auth)"
    r"[a-z0-9_.\[\]-]*|"
    r"[a-z0-9_.\[\]-]*(?:api|access|private|signing|encryption|aws|session)"
    r"[ _.-]?key[a-z0-9_.\[\]-]*|"
    r"auth(?:orization)?|pwd|session(?:[ _.-]?id)?"
    r")[\"']?\s*[:=]\s*"
    r"[^\r\n]*"
)
_IDENTITY_ASSIGNMENT_RE = re.compile(
    r"(?i)(?<![a-z0-9_])[\"']?"
    r"(computer[ _.-]?name|host(?:[ _.-]?name)?|user(?:[ _.-]?name)?|usuario)"
    r"[\"']?\s*[:=]\s*[^\r\n]*"
)
_ENV_PATH_RE = re.compile(
    r"(?i)%(?:USERPROFILE|LOCALAPPDATA|APPDATA|TEMP|TMP|HOMEDRIVE|HOMEPATH)%"
    r"[^\r\n]*"
)
_QUOTED_ABSOLUTE_PATH_RE = re.compile(
    r"(?i)([\"'])(?:[A-Z]:[\\/]|\\\\|/(?!/))[^\"'\r\n]+\1"
)
_WINDOWS_PATH_RE = re.compile(
    r"(?im)(?<![A-Za-z0-9])(?:[A-Z]:[\\/]|\\\\)[^\r\n]*"
)
_WINDOWS_ROOT_PATH_RE = re.compile(
    r"(?im)(?<![A-Za-z0-9_\\])\\(?!\\)[^\r\n]*"
)
_NETWORK_PATH_RE = re.compile(r"(?m)(?<!:)//[^\r\n]*")
_HOME_PATH_RE = re.compile(r"(?im)(?<![A-Za-z0-9])~[\\/][^\r\n]*")
_POSIX_PATH_RE = re.compile(
    r"(?m)(?<![A-Za-z0-9_/.])/(?!/)[^\r\n]*"
)
_TRACEBACK_MARKER = "Traceback (most recent call last):"
_AT_MENTION_RE = re.compile(r"(?<![\w@])@[A-Za-z0-9_-]{1,39}\b")


def _replacement_with_label(match: re.Match[str], label: str) -> str:
    key = match.group(1)
    return f"{key}=[{label}]"


def _truncate(value: str, max_chars: int) -> str:
    if max_chars < 1:
        return ""
    if len(value) <= max_chars:
        return value
    marker = "... [TRUNCADO]"
    if max_chars <= len(marker):
        return marker[:max_chars]
    return value[: max_chars - len(marker)] + marker


def sanitize_text(value: object, *, max_chars: int = MAX_GENERIC_FIELD_CHARS) -> str:
    """Remove dados pessoais, caminhos e segredos de um campo livre.

    A funcao favorece privacidade em vez de preservar cada palavra: ao achar um
    caminho absoluto sem aspas, ela pode ocultar tambem o restante da frase.
    """

    if value is None:
        return ""
    text = str(value)[:_MAX_SANITIZER_INPUT_CHARS]
    if _TRACEBACK_MARKER.casefold() in text.casefold():
        marker_at = text.casefold().find(_TRACEBACK_MARKER.casefold())
        text = text[:marker_at] + "[TRACEBACK OMITIDO]"
    text = _CONTROL_CHARACTER_RE.sub(" ", text)
    text = _URL_RE.sub("[URL]", text)
    text = _BEARER_RE.sub("Bearer [SEGREDO]", text)
    text = _SECRET_ASSIGNMENT_RE.sub(
        lambda match: _replacement_with_label(match, "SEGREDO"), text
    )
    text = _IDENTITY_ASSIGNMENT_RE.sub(
        lambda match: _replacement_with_label(match, "IDENTIDADE"), text
    )
    text = _KNOWN_TOKEN_RE.sub("[SEGREDO]", text)
    text = _JWT_RE.sub("[SEGREDO]", text)
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _STEAM_ID_ASSIGNMENT_RE.sub("SteamID=[STEAM_ID]", text)
    text = _STEAM_ID_RE.sub("[STEAM_ID]", text)
    text = _AT_MENTION_RE.sub("[MENCAO]", text)
    text = _ENV_PATH_RE.sub("[CAMINHO]", text)
    text = _QUOTED_ABSOLUTE_PATH_RE.sub("[CAMINHO]", text)
    text = _WINDOWS_PATH_RE.sub("[CAMINHO]", text)
    text = _WINDOWS_ROOT_PATH_RE.sub("[CAMINHO]", text)
    text = _NETWORK_PATH_RE.sub("[CAMINHO]", text)
    text = _HOME_PATH_RE.sub("[CAMINHO]", text)
    text = _POSIX_PATH_RE.sub("[CAMINHO]", text)
    return _truncate(text.strip(), max_chars)


def _collect_game_files(game_dir: Path | None) -> dict[str, object]:
    """Do not probe game files until a handle-relative scanner is available.

    Path-based checks cannot rule out a concurrent junction swap before a later
    open.  The report deliberately keeps this section empty instead of risking
    access to an unexpected local or network target.
    """

    if game_dir is None:
        return {"scan_status": "not_requested", "items": []}
    return {"scan_status": "disabled_for_race_safety", "items": []}


def _sanitized_build_ids(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if len(result) >= 32:
            break
        cleaned = sanitize_text(value, max_chars=64)
        if cleaned:
            result.append(cleaned)
    return sorted(set(result))


def _sanitized_log(lines: Iterable[str]) -> list[str]:
    tail: deque[str] = deque(maxlen=MAX_LOG_LINES)
    omitting_traceback = False
    for raw_line in lines:
        line = str(raw_line)
        if _TRACEBACK_MARKER.casefold() in line.casefold():
            if not omitting_traceback:
                tail.append("[TRACEBACK OMITIDO]")
            omitting_traceback = True
            continue
        if omitting_traceback:
            # Application log records begin with a bracket or an ISO-like date.
            # Everything else after a traceback marker is safer to omit.
            if not re.match(r"^(?:\[[A-Za-z]+\]|\d{4}-\d{2}-\d{2}[ T])", line):
                continue
            omitting_traceback = False
        cleaned = sanitize_text(line, max_chars=MAX_LOG_LINE_CHARS)
        if cleaned:
            tail.append(cleaned)

    kept_reversed: list[str] = []
    used = 0
    for line in reversed(tail):
        extra = len(line) + (1 if kept_reversed else 0)
        if used + extra > MAX_LOG_TOTAL_CHARS:
            break
        kept_reversed.append(line)
        used += extra
    return list(reversed(kept_reversed))


def _bounded_nonnegative_int(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return max(0, min(parsed, (1 << 63) - 1))


def _encode_bounded_report(report: dict[str, object]) -> str:
    def encode() -> str:
        return json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    result = encode()
    if len(result.encode("utf-8")) <= MAX_REPORT_BYTES:
        return result

    report["recent_log"] = ["[LOG OMITIDO: limite do relatorio]"]
    result = encode()
    if len(result.encode("utf-8")) <= MAX_REPORT_BYTES:
        return result

    error = report.get("error")
    if isinstance(error, dict):
        error["message"] = "[MENSAGEM OMITIDA: limite do relatorio]"
    game_files = report.get("game_files")
    if isinstance(game_files, dict):
        items = game_files.get("items")
        if isinstance(items, list) and len(items) > 16:
            game_files["items_omitted"] = len(items) - 16
            game_files["items"] = items[:16]
    result = encode()
    if len(result.encode("utf-8")) > MAX_REPORT_BYTES:
        raise ValueError("O relatorio sanitizado excedeu o limite seguro.")
    return result


def build_diagnostic_report(
    *,
    patcher_version: str,
    operation: str,
    stage: str,
    status: str,
    error_code: str | None,
    error_kind: str | None,
    error_message: str | None,
    supported_game_version: str,
    supported_build_ids: Iterable[str],
    detected_build_id: str | None,
    build_status: str,
    stage_elapsed_seconds: int | None = None,
    progress_current: int | None = None,
    progress_total: int | None = None,
    game_write_state: str | None = None,
    game_dir: Path | None = None,
    log_lines: Iterable[str] = (),
) -> str:
    """Build a bounded JSON report; no upload or filesystem write is performed."""

    report = {
        "schema": REPORT_SCHEMA,
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": str(uuid.uuid4()),
        "created_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "patcher": {
            "version": sanitize_text(patcher_version),
        },
        "operation": {
            "name": sanitize_text(operation),
            "stage": sanitize_text(stage),
            "status": sanitize_text(status),
            "stage_elapsed_seconds": _bounded_nonnegative_int(
                stage_elapsed_seconds
            ),
            "progress": {
                "current": _bounded_nonnegative_int(progress_current),
                "total": _bounded_nonnegative_int(progress_total),
            },
            "game_write_state": sanitize_text(game_write_state) or None,
        },
        "error": {
            "code": sanitize_text(error_code, max_chars=64) or None,
            "kind": sanitize_text(error_kind) or None,
            "message": sanitize_text(
                error_message,
                max_chars=MAX_ERROR_MESSAGE_CHARS,
            )
            or None,
        },
        "compatibility": {
            "supported_game_version": sanitize_text(supported_game_version),
            "supported_steam_build_ids": _sanitized_build_ids(supported_build_ids),
            "detected_steam_build_id": sanitize_text(
                detected_build_id,
                max_chars=64,
            )
            or None,
            "build_detection_status": sanitize_text(build_status),
        },
        "runtime": {
            "operating_system": sanitize_text(platform.system()),
            "os_release": sanitize_text(platform.release()),
            "architecture": sanitize_text(platform.machine()),
            "python_version": platform.python_version(),
        },
        "game_files": _collect_game_files(game_dir),
        "recent_log": _sanitized_log(log_lines),
        "privacy": {
            "automatic_upload": False,
            "absolute_game_path_included": False,
            "diagnostic_network_access": False,
            "game_files_inspected": False,
            "manifest_content_included": False,
            "save_files_included": False,
        },
    }
    return _encode_bounded_report(report)


__all__ = [
    "MAX_REPORT_BYTES",
    "REPORT_SCHEMA",
    "REPORT_SCHEMA_VERSION",
    "build_diagnostic_report",
    "sanitize_text",
]
