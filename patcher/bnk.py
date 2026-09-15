"""Structural Wwise BNK merge for a future corrected ERPT-BR installer.

The translation payload can be older than the user's game build.  Replacing a
whole bank in that situation also removes events and embedded media introduced
by the game update.  This module treats the vanilla bank as the authority for
its structure and only imports translated sound objects/media that already
exist in that bank.  The recovery-only 0.9.3 release does not activate it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


_SINGLETON_CHUNKS = frozenset({b"BKHD", b"DIDX", b"DATA", b"HIRC", b"STID"})
_U32_MAX = (1 << 32) - 1


class BnkMergeError(ValueError):
    """A bank is malformed or cannot safely be merged with its baseline."""


@dataclass(frozen=True)
class BnkSection:
    chunk_id: bytes
    data: bytes


@dataclass(frozen=True)
class HircObject:
    type_id: int
    object_id: int
    raw: bytes


@dataclass(frozen=True)
class _Media:
    media_id: int
    offset: int
    data: bytes


def _u32(data: bytes, offset: int, label: str) -> int:
    if offset < 0 or offset + 4 > len(data):
        raise BnkMergeError(f"{label} truncado no offset {offset}.")
    return struct.unpack_from("<I", data, offset)[0]


def parse_bnk(data: bytes) -> tuple[BnkSection, ...]:
    """Parse all top-level chunks, rejecting truncation and ambiguous chunks."""

    if not data:
        raise BnkMergeError("BNK vazio.")

    sections: list[BnkSection] = []
    counts: dict[bytes, int] = {}
    offset = 0
    while offset < len(data):
        if offset + 8 > len(data):
            raise BnkMergeError(
                f"Cabecalho de secao BNK truncado no offset {offset}."
            )
        chunk_id = data[offset : offset + 4]
        if any(value < 0x20 or value > 0x7E for value in chunk_id):
            raise BnkMergeError(
                f"Identificador de secao BNK invalido no offset {offset}: "
                f"{chunk_id!r}."
            )
        size = _u32(data, offset + 4, f"Tamanho da secao {chunk_id!r}")
        data_start = offset + 8
        data_end = data_start + size
        if data_end > len(data):
            raise BnkMergeError(
                f"Secao {chunk_id!r} ultrapassa o fim do BNK "
                f"({data_end} > {len(data)})."
            )
        sections.append(BnkSection(chunk_id, data[data_start:data_end]))
        counts[chunk_id] = counts.get(chunk_id, 0) + 1
        if chunk_id in _SINGLETON_CHUNKS and counts[chunk_id] > 1:
            raise BnkMergeError(f"Secao BNK duplicada: {chunk_id!r}.")
        offset = data_end

    if not sections or sections[0].chunk_id != b"BKHD":
        raise BnkMergeError("BKHD precisa ser a primeira secao do BNK.")
    if counts.get(b"BKHD") != 1:
        raise BnkMergeError("BNK precisa conter exatamente uma secao BKHD.")
    if counts.get(b"HIRC") != 1:
        raise BnkMergeError("BNK precisa conter exatamente uma secao HIRC.")
    if (counts.get(b"DIDX", 0), counts.get(b"DATA", 0)) not in {
        (0, 0),
        (1, 1),
    }:
        raise BnkMergeError("DIDX e DATA precisam existir juntos e sem duplicatas.")
    return tuple(sections)


def parse_hirc(data: bytes) -> tuple[HircObject, ...]:
    """Parse a HIRC body and retain each object's exact serialized bytes."""

    count = _u32(data, 0, "Contagem HIRC")
    # Every object needs one type byte, a u32 length and at least a u32 id.
    maximum_count = (len(data) - 4) // 9
    if count > maximum_count:
        raise BnkMergeError(
            f"Contagem HIRC impossivel ({count} objetos em {len(data)} bytes)."
        )

    result: list[HircObject] = []
    type_two_ids: set[int] = set()
    offset = 4
    for index in range(count):
        if offset + 5 > len(data):
            raise BnkMergeError(f"Objeto HIRC[{index}] truncado.")
        type_id = data[offset]
        object_size = _u32(data, offset + 1, f"Tamanho HIRC[{index}]")
        if object_size < 4:
            raise BnkMergeError(
                f"Objeto HIRC[{index}] nao possui id de 32 bits."
            )
        end = offset + 5 + object_size
        if end > len(data):
            raise BnkMergeError(
                f"Objeto HIRC[{index}] ultrapassa o fim da secao."
            )
        object_id = _u32(data, offset + 5, f"Id HIRC[{index}]")
        if type_id == 2:
            if object_id in type_two_ids:
                raise BnkMergeError(
                    f"Objeto Sound HIRC Type=2 duplicado: {object_id}."
                )
            type_two_ids.add(object_id)
        result.append(HircObject(type_id, object_id, data[offset:end]))
        offset = end

    if offset != len(data):
        raise BnkMergeError(
            f"HIRC possui {len(data) - offset} bytes fora da lista de objetos."
        )
    return tuple(result)


def _section_map(sections: tuple[BnkSection, ...]) -> dict[bytes, BnkSection]:
    return {section.chunk_id: section for section in sections}


def _validate_bank_identity(
    vanilla_sections: dict[bytes, BnkSection],
    payload_sections: dict[bytes, BnkSection],
) -> None:
    vanilla_header = vanilla_sections[b"BKHD"].data
    payload_header = payload_sections[b"BKHD"].data
    if len(vanilla_header) < 8 or len(payload_header) < 8:
        raise BnkMergeError("BKHD truncado: versao e bank id sao obrigatorios.")
    vanilla_identity = struct.unpack_from("<II", vanilla_header)
    payload_identity = struct.unpack_from("<II", payload_header)
    if vanilla_identity != payload_identity:
        raise BnkMergeError(
            "Payload pertence a outro banco ou versao Wwise "
            f"(vanilla={vanilla_identity}, payload={payload_identity})."
        )


def _merge_hirc(vanilla_data: bytes, payload_data: bytes) -> bytes:
    vanilla_objects = parse_hirc(vanilla_data)
    payload_objects = parse_hirc(payload_data)
    payload_sounds = {
        item.object_id: item.raw for item in payload_objects if item.type_id == 2
    }

    merged_objects = [
        payload_sounds.get(item.object_id, item.raw)
        if item.type_id == 2
        else item.raw
        for item in vanilla_objects
    ]
    result = bytearray(struct.pack("<I", len(merged_objects)))
    for raw in merged_objects:
        result.extend(raw)
    return bytes(result)


def _parse_media(didx: bytes, data: bytes, label: str) -> tuple[_Media, ...]:
    if len(didx) % 12:
        raise BnkMergeError(
            f"DIDX {label} possui tamanho invalido ({len(didx)} bytes)."
        )

    result: list[_Media] = []
    media_ids: set[int] = set()
    previous_end = 0
    for index, offset in enumerate(range(0, len(didx), 12)):
        media_id, data_offset, size = struct.unpack_from("<III", didx, offset)
        if media_id in media_ids:
            raise BnkMergeError(f"Media DIDX {label} duplicada: {media_id}.")
        media_ids.add(media_id)
        end = data_offset + size
        if data_offset < previous_end:
            raise BnkMergeError(
                f"DIDX {label}[{index}] sobrepoe ou sai da ordem anterior."
            )
        if end > len(data):
            raise BnkMergeError(
                f"DIDX {label}[{index}] ultrapassa DATA ({end} > {len(data)})."
            )
        if any(data[previous_end:data_offset]):
            raise BnkMergeError(
                f"Padding DATA {label} antes da media {media_id} nao e zero."
            )
        result.append(_Media(media_id, data_offset, data[data_offset:end]))
        previous_end = end

    if any(data[previous_end:]):
        raise BnkMergeError(f"Padding final DATA {label} nao e zero.")
    return tuple(result)


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _uses_alignment(media: tuple[_Media, ...], alignment: int) -> bool:
    cursor = 0
    for item in media:
        if item.offset != _align_up(cursor, alignment):
            return False
        cursor = item.offset + len(item.data)
    return True


def _infer_alignment(media: tuple[_Media, ...]) -> int:
    # Elden Ring's Wwise banks use 16-byte DATA alignment.  Prefer the observed
    # 16-byte layout; for a nonstandard but structurally valid bank infer the
    # largest power-of-two alignment represented by its offsets.  With fewer
    # than two media items there is no evidence, so the game default wins.
    if len(media) < 2 or _uses_alignment(media, 16):
        return 16
    for alignment in (4096, 2048, 1024, 512, 256, 128, 64, 32, 8, 4, 2, 1):
        if _uses_alignment(media, alignment):
            return alignment
    raise BnkMergeError("Nao foi possivel inferir o alinhamento de DATA vanilla.")


def _merge_media(
    vanilla_didx: bytes,
    vanilla_data: bytes,
    payload_didx: bytes,
    payload_data: bytes,
) -> tuple[bytes, bytes]:
    vanilla_media = _parse_media(vanilla_didx, vanilla_data, "vanilla")
    payload_media = _parse_media(payload_didx, payload_data, "do payload")
    payload_by_id = {item.media_id: item.data for item in payload_media}

    replacements = {
        item.media_id: payload_by_id[item.media_id]
        for item in vanilla_media
        if item.media_id in payload_by_id
    }
    if not replacements or all(
        replacements.get(item.media_id, item.data) == item.data
        for item in vanilla_media
    ):
        return vanilla_didx, vanilla_data

    alignment = _infer_alignment(vanilla_media)
    merged_didx = bytearray()
    merged_data = bytearray()
    for item in vanilla_media:
        offset = _align_up(len(merged_data), alignment)
        merged_data.extend(b"\0" * (offset - len(merged_data)))
        media_data = replacements.get(item.media_id, item.data)
        if offset > _U32_MAX or len(media_data) > _U32_MAX:
            raise BnkMergeError("DIDX mesclado excede o limite de 32 bits.")
        merged_didx.extend(struct.pack("<III", item.media_id, offset, len(media_data)))
        merged_data.extend(media_data)
    return bytes(merged_didx), bytes(merged_data)


def _serialize_sections(sections: tuple[BnkSection, ...]) -> bytes:
    result = bytearray()
    for section in sections:
        if len(section.data) > _U32_MAX:
            raise BnkMergeError(f"Secao {section.chunk_id!r} excede 4 GiB.")
        result.extend(section.chunk_id)
        result.extend(struct.pack("<I", len(section.data)))
        result.extend(section.data)
    return bytes(result)


def merge_bnk_with_vanilla(vanilla: bytes, payload: bytes) -> bytes:
    """Merge translated sound data into a bank without deleting vanilla data.

    The output keeps the vanilla chunk order, BKHD/STID/unknown chunks, complete
    HIRC object set, and complete embedded-media id set.  Payload-only objects
    are deliberately ignored because they are not referenced by the target
    game's vanilla bank.
    """

    vanilla_sections = parse_bnk(vanilla)
    payload_sections = parse_bnk(payload)
    vanilla_by_id = _section_map(vanilla_sections)
    payload_by_id = _section_map(payload_sections)
    _validate_bank_identity(vanilla_by_id, payload_by_id)

    replacements: dict[bytes, bytes] = {
        b"HIRC": _merge_hirc(
            vanilla_by_id[b"HIRC"].data,
            payload_by_id[b"HIRC"].data,
        )
    }
    if b"DIDX" in vanilla_by_id and b"DIDX" in payload_by_id:
        merged_didx, merged_data = _merge_media(
            vanilla_by_id[b"DIDX"].data,
            vanilla_by_id[b"DATA"].data,
            payload_by_id[b"DIDX"].data,
            payload_by_id[b"DATA"].data,
        )
        replacements[b"DIDX"] = merged_didx
        replacements[b"DATA"] = merged_data

    merged_sections = tuple(
        BnkSection(section.chunk_id, replacements.get(section.chunk_id, section.data))
        for section in vanilla_sections
    )
    return _serialize_sections(merged_sections)
