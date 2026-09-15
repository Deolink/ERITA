from __future__ import annotations

import struct
import unittest

from patcher import bnk, engine


def section(chunk_id: bytes, data: bytes) -> bytes:
    return chunk_id + struct.pack("<I", len(data)) + data


def make_hirc(objects: list[tuple[int, int, bytes]]) -> bytes:
    result = bytearray(struct.pack("<I", len(objects)))
    for type_id, object_id, body in objects:
        payload = struct.pack("<I", object_id) + body
        result.extend(bytes((type_id,)))
        result.extend(struct.pack("<I", len(payload)))
        result.extend(payload)
    return bytes(result)


def make_media(items: list[tuple[int, bytes]]) -> tuple[bytes, bytes]:
    didx = bytearray()
    data = bytearray()
    for media_id, media_data in items:
        offset = (len(data) + 15) // 16 * 16
        data.extend(b"\0" * (offset - len(data)))
        didx.extend(struct.pack("<III", media_id, offset, len(media_data)))
        data.extend(media_data)
    return bytes(didx), bytes(data)


def make_bank(
    *,
    objects: list[tuple[int, int, bytes]],
    media: list[tuple[int, bytes]] | None = None,
    header_tail: bytes = b"",
    stid: bytes | None = None,
    unknown: bytes | None = None,
    version: int = 135,
    bank_id: int = 7,
) -> bytes:
    parts = [section(b"BKHD", struct.pack("<II", version, bank_id) + header_tail)]
    if media is not None:
        didx, data = make_media(media)
        parts.extend((section(b"DIDX", didx), section(b"DATA", data)))
    if unknown is not None:
        parts.append(section(b"ENVS", unknown))
    parts.append(section(b"HIRC", make_hirc(objects)))
    if stid is not None:
        parts.append(section(b"STID", stid))
    return b"".join(parts)


def sections_by_id(data: bytes) -> dict[bytes, bnk.BnkSection]:
    return {item.chunk_id: item for item in bnk.parse_bnk(data)}


def media_by_id(data: bytes) -> dict[int, bytes]:
    sections = sections_by_id(data)
    didx = sections[b"DIDX"].data
    media_data = sections[b"DATA"].data
    result = {}
    for offset in range(0, len(didx), 12):
        media_id, data_offset, size = struct.unpack_from("<III", didx, offset)
        result[media_id] = media_data[data_offset : data_offset + size]
    return result


class SafeBnkMergeTests(unittest.TestCase):
    def test_engine_helper_decrypts_merges_and_reencrypts_staging_slot(self) -> None:
        vanilla = make_bank(objects=[(2, 10, b"old")])
        payload = make_bank(objects=[(2, 10, b"new")])
        padded_size = (len(vanilla) + 15) // 16 * 16
        key = bytes.fromhex("000102030405060708090a0b0c0d0e0f")
        aes_ranges = (engine.AESRange(0, padded_size),)
        encrypted_baseline = bytearray(
            vanilla + b"\0" * (padded_size - len(vanilla))
        )
        engine.encrypt_aes_ecb(encrypted_baseline, key, aes_ranges)
        entry = engine.FileEntry(
            file_name_hash=1,
            padded_file_size=padded_size,
            unpadded_file_size=len(vanilla),
            file_offset=0,
            sha_hash_offset=0,
            aes_key_offset=1,
            aes_info=engine.AESKeyInfo(key, aes_ranges),
        )

        prepared = engine.prepare_bnk_slot_from_baseline(
            payload,
            bytes(encrypted_baseline),
            entry,
        )

        decrypted = engine.decrypt_aes_ecb(bytearray(prepared), key, aes_ranges)
        expected = bnk.merge_bnk_with_vanilla(vanilla, payload)
        self.assertEqual(bytes(decrypted[: len(expected)]), expected)
        self.assertEqual(bytes(decrypted[len(expected) :]), b"\0" * (padded_size - len(expected)))

    def test_cs_main_like_merge_restores_new_vanilla_objects_and_media(self) -> None:
        # This reproduces the important 1.17.1 regression shape: the newer
        # vanilla cs_main has three DIDX entries and 234 HIRC objects that the
        # older translation payload does not know about.
        new_vanilla_objects = [
            (3, 1_000 + index, f"vanilla-{index}".encode())
            for index in range(234)
        ]
        vanilla = make_bank(
            objects=[(2, 10, b"old-sound-object"), *new_vanilla_objects],
            media=[
                (10, b"old-audio"),
                (20, b"new-media-one"),
                (30, b"new-media-two"),
                (40, b"new-media-three"),
            ],
            header_tail=b"vanilla-bkhd",
            stid=b"vanilla-stid",
            unknown=b"vanilla-envs",
        )
        payload = make_bank(
            objects=[
                (2, 10, b"translated-sound-object"),
                (2, 999, b"payload-only-object"),
            ],
            media=[
                (10, b"translated-audio"),
                (999, b"payload-only-media"),
            ],
            header_tail=b"stale-payload-bkhd",
            stid=b"stale-payload-stid",
            unknown=b"stale-payload-envs",
        )

        merged = bnk.merge_bnk_with_vanilla(vanilla, payload)

        vanilla_sections = sections_by_id(vanilla)
        merged_sections = sections_by_id(merged)
        self.assertEqual(
            [item.chunk_id for item in bnk.parse_bnk(merged)],
            [item.chunk_id for item in bnk.parse_bnk(vanilla)],
        )
        self.assertEqual(merged_sections[b"BKHD"], vanilla_sections[b"BKHD"])
        self.assertEqual(merged_sections[b"STID"], vanilla_sections[b"STID"])
        self.assertEqual(merged_sections[b"ENVS"], vanilla_sections[b"ENVS"])

        merged_objects = bnk.parse_hirc(merged_sections[b"HIRC"].data)
        vanilla_objects = bnk.parse_hirc(vanilla_sections[b"HIRC"].data)
        self.assertEqual(len(merged_objects), 235)
        self.assertEqual(
            [(item.type_id, item.object_id) for item in merged_objects],
            [(item.type_id, item.object_id) for item in vanilla_objects],
        )
        self.assertIn(b"translated-sound-object", merged_objects[0].raw)
        self.assertNotIn(999, {item.object_id for item in merged_objects})
        self.assertEqual(
            [item.raw for item in merged_objects[1:]],
            [item.raw for item in vanilla_objects[1:]],
        )

        merged_media = media_by_id(merged)
        self.assertEqual(set(merged_media), {10, 20, 30, 40})
        self.assertEqual(merged_media[10], b"translated-audio")
        self.assertEqual(merged_media[20], b"new-media-one")
        self.assertEqual(merged_media[30], b"new-media-two")
        self.assertEqual(merged_media[40], b"new-media-three")

    def test_only_shared_type_two_objects_are_replaced(self) -> None:
        vanilla = make_bank(
            objects=[(2, 10, b"old-sound"), (3, 10, b"old-event")],
        )
        payload = make_bank(
            objects=[(2, 10, b"new-sound"), (3, 10, b"new-event")],
        )

        merged = bnk.merge_bnk_with_vanilla(vanilla, payload)
        objects = bnk.parse_hirc(sections_by_id(merged)[b"HIRC"].data)

        self.assertIn(b"new-sound", objects[0].raw)
        self.assertIn(b"old-event", objects[1].raw)
        self.assertNotIn(b"new-event", objects[1].raw)

    def test_bank_without_embedded_media_stays_without_media(self) -> None:
        vanilla = make_bank(objects=[(2, 10, b"old")])
        payload = make_bank(
            objects=[(2, 10, b"translated")],
            media=[(10, b"unreferenced-media")],
        )

        merged = bnk.merge_bnk_with_vanilla(vanilla, payload)
        sections = sections_by_id(merged)

        self.assertNotIn(b"DIDX", sections)
        self.assertNotIn(b"DATA", sections)
        self.assertIn(
            b"translated",
            bnk.parse_hirc(sections[b"HIRC"].data)[0].raw,
        )

    def test_rejects_different_bank_identity(self) -> None:
        vanilla = make_bank(objects=[], bank_id=7)
        payload = make_bank(objects=[], bank_id=8)

        with self.assertRaisesRegex(bnk.BnkMergeError, "outro banco"):
            bnk.merge_bnk_with_vanilla(vanilla, payload)

    def test_rejects_hirc_tail_not_declared_in_object_count(self) -> None:
        malformed_hirc = make_hirc([]) + b"junk"
        malformed = section(b"BKHD", struct.pack("<II", 135, 7)) + section(
            b"HIRC", malformed_hirc
        )

        with self.assertRaisesRegex(bnk.BnkMergeError, "fora da lista"):
            bnk.merge_bnk_with_vanilla(malformed, malformed)

    def test_rejects_nonzero_data_padding(self) -> None:
        didx = struct.pack("<III", 10, 1, 1)
        malformed = (
            section(b"BKHD", struct.pack("<II", 135, 7))
            + section(b"DIDX", didx)
            + section(b"DATA", b"XA")
            + section(b"HIRC", make_hirc([]))
        )

        with self.assertRaisesRegex(bnk.BnkMergeError, "nao e zero"):
            bnk.merge_bnk_with_vanilla(malformed, malformed)


if __name__ == "__main__":
    unittest.main()
