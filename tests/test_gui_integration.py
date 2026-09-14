from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest import mock

from patcher import patcher_gui


class GuiIntegrationTests(unittest.TestCase):
    def test_authenticated_plan_covers_alias_not_selected_for_writing(self) -> None:
        selected = mock.Mock()
        selected.replacement.source_relative = "enus/voice.bnk"
        selected.source_sha256 = "a" * 64
        plan = mock.Mock()
        plan.payload_file_sha256 = (
            ("voice.bnk", "a" * 64),
            ("enus/voice.bnk", "a" * 64),
        )
        plan.payload_file_count = 2
        plan.matched_file_count = 2
        plan.writes = (selected,)
        patch_engine = mock.Mock()
        patch_engine.build_plan.return_value = plan

        with mock.patch.object(
            patcher_gui,
            "validate_patch_directory",
        ) as validate:
            result = patcher_gui.build_authenticated_plan(
                patch_engine,
                Path("payload"),
            )

        self.assertIs(result, plan)
        self.assertEqual(
            validate.call_args.kwargs["expected_file_sha256"],
            {
                "voice.bnk": "a" * 64,
                "enus/voice.bnk": "a" * 64,
            },
        )

    def test_reads_and_requires_the_pinned_steam_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            steamapps = Path(temporary) / "steamapps"
            game = steamapps / "common" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"AppState"\n{\n  "buildid"  "25080141"\n}\n',
                encoding="utf-8",
            )

            self.assertEqual(patcher_gui.steam_build_id(game), "25080141")
            self.assertEqual(patcher_gui.require_supported_build(game), "25080141")

    def test_rejects_a_different_steam_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            steamapps = Path(temporary) / "steamapps"
            game = steamapps / "common" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"buildid" "99999999"\n', encoding="utf-8"
            )

            with self.assertRaisesRegex(
                patcher_gui.CompatibilityError, "Nenhum arquivo foi alterado"
            ):
                patcher_gui.require_supported_build(game)

    def test_optional_movie_payload_is_detected_before_install(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "movie").mkdir()
            (root / "movie" / "intro.bk2").write_bytes(b"untrusted")

            self.assertTrue(patcher_gui.optional_movie_payload_present(root))

    def test_empty_movie_directory_is_not_treated_as_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "movie_dlc").mkdir()

            self.assertFalse(patcher_gui.optional_movie_payload_present(root))

    def test_legacy_movie_sidecar_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            game = Path(temporary)
            sidecar = game / "movie" / "intro.bk2.original"
            sidecar.parent.mkdir()
            sidecar.write_bytes(b"legacy")

            self.assertEqual(patcher_gui.legacy_movie_sidecars(game), [sidecar])

    def test_process_detection_failure_blocks_writes_on_windows(self) -> None:
        with (
            mock.patch.object(patcher_gui.sys, "platform", "win32"),
            mock.patch.object(
                patcher_gui.subprocess,
                "run",
                side_effect=OSError("tasklist unavailable"),
            ),
        ):
            with self.assertRaisesRegex(
                patcher_gui.PatcherError, "Nenhum arquivo sera alterado"
            ):
                patcher_gui.running_blockers()


if __name__ == "__main__":
    unittest.main()
