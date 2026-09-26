from __future__ import annotations

from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

from patcher import patcher_gui


class GuiIntegrationTests(unittest.TestCase):
    def test_v097_production_installation_is_enabled(self) -> None:
        self.assertEqual(patcher_gui.PATCHER_VERSION, "0.9.7")
        self.assertFalse(patcher_gui.INSTALLATION_SUSPENDED)

    def test_success_message_never_treats_appmanifest_as_online_proof(self) -> None:
        message = patcher_gui.INSTALLATION_SUCCESS_MESSAGE

        self.assertIn("appmanifest e apenas informativo", message)
        self.assertIn("confirme que a Steam reconhece", message)
        self.assertNotIn("online confirmado", message.casefold())

    def test_startup_does_not_block_a_conflicting_optional_manifest(self) -> None:
        app = mock.Mock()
        info = patcher_gui.SteamBuildInfo("99999999", "identified")

        with mock.patch.object(
            patcher_gui,
            "validate_game_archive_profile",
            return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
        ):
            patcher_gui.PatcherApp._finish_startup_status(
                app, Path("selected-game"), info
            )

        app._set_stage.assert_called_once_with(
            "ready",
            "Pre-verificacao dos arquivos concluida; manifesto opcional e "
            "Steam/online nao confirmados. Pronto para a validacao completa.",
            finished=True,
        )
        app._record_error.assert_not_called()

    def test_startup_accepts_authenticated_files_when_manifest_is_missing(
        self,
    ) -> None:
        app = mock.Mock()
        info = patcher_gui.SteamBuildInfo(None, "manifest_missing")

        with mock.patch.object(
            patcher_gui,
            "validate_game_archive_profile",
            return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
        ):
            patcher_gui.PatcherApp._finish_startup_status(
                app, Path("selected-game"), info
            )

        app._set_stage.assert_called_once_with(
            "ready",
            "Pre-verificacao dos arquivos concluida; manifesto opcional e "
            "Steam/online nao confirmados. Pronto para a validacao completa.",
            finished=True,
        )
        app._record_error.assert_not_called()

    def test_startup_labels_only_the_pinned_build_as_ready(self) -> None:
        app = mock.Mock()
        info = patcher_gui.SteamBuildInfo("25080141", "identified")

        with mock.patch.object(patcher_gui, "INSTALLATION_SUSPENDED", False):
            with mock.patch.object(
                patcher_gui,
                "validate_game_archive_profile",
                return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
            ):
                patcher_gui.PatcherApp._finish_startup_status(
                    app, Path("selected-game"), info
                )

        app._record_error.assert_not_called()
        app._set_stage.assert_called_once_with(
            "ready",
            "Pre-verificacao dos arquivos concluida; o manifesto informa o BuildID "
            "esperado, mas nao confirma Steam/online. Pronto para a validacao completa.",
            finished=True,
        )

    def test_startup_rejects_real_files_outside_the_profile(self) -> None:
        app = mock.Mock()
        info = patcher_gui.SteamBuildInfo("25080141", "identified")

        with mock.patch.object(
            patcher_gui,
            "validate_game_archive_profile",
            side_effect=patcher_gui.CompatibilityError("sd.bhd divergente"),
        ):
            patcher_gui.PatcherApp._finish_startup_status(
                app, Path("selected-game"), info
            )

        app._set_stage.assert_called_once_with(
            "game_files_unsupported",
            "Arquivos do jogo nao homologados [ERPT-FILES-001]; "
            "abra Diagnostico para copiar o relatorio.",
            finished=True,
        )
        recorded = app._record_error.call_args.args[0]
        self.assertIsInstance(recorded, patcher_gui.GameFilesCompatibilityError)
        self.assertIn("sd.bhd divergente", str(recorded))

    @staticmethod
    def _diagnostic_state_stub() -> patcher_gui.PatcherApp:
        app = object.__new__(patcher_gui.PatcherApp)
        app._diagnostic_lock = threading.Lock()
        app._diagnostic_operation = "install"
        app._diagnostic_stage = "steam_build"
        app._diagnostic_stage_started = 10.0
        app._diagnostic_stage_elapsed = None
        app._diagnostic_write_state = "not_started"
        app._diagnostic_progress = (0, 0)
        app._detected_build_id = "11111111"
        app._build_read_status = "identified"
        app._detected_build_path_key = None
        app._last_error_code = None
        app._last_error_kind = None
        app._last_error_message = None
        app._log_history = []
        app._diagnostic_status = "Identificando"
        return app

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

    def test_close_is_safe_while_diagnostic_collection_finishes(self) -> None:
        app = object.__new__(patcher_gui.PatcherApp)
        app._busy = False
        app._report_collecting = 1
        app._closing = False
        app.destroy = mock.Mock()

        patcher_gui.PatcherApp._on_close(app)

        self.assertTrue(app._closing)
        app.destroy.assert_called_once_with()

    def test_ui_discards_callbacks_after_window_starts_closing(self) -> None:
        app = object.__new__(patcher_gui.PatcherApp)
        app._closing = True
        app.after = mock.Mock()

        patcher_gui.PatcherApp._ui(app, mock.Mock())

        app.after.assert_not_called()

    def test_ui_discards_an_already_queued_callback_after_close(self) -> None:
        app = object.__new__(patcher_gui.PatcherApp)
        app._closing = False
        queued: list[object] = []
        app.after = lambda _delay, callback: queued.append(callback)
        callback = mock.Mock()

        patcher_gui.PatcherApp._ui(app, callback)
        app._closing = True
        queued[0]()

        callback.assert_not_called()

    @unittest.skipUnless(
        patcher_gui.sys.platform == "win32",
        "Registro da Steam existe apenas no Windows",
    )
    def test_steam_roots_accepts_user_steam_path_without_install_path(self) -> None:
        import winreg

        key = mock.MagicMock()
        key.__enter__.return_value = key

        def open_key(hive: object, subkey: str) -> object:
            if (
                hive == winreg.HKEY_CURRENT_USER
                and subkey == r"SOFTWARE\Valve\Steam"
            ):
                return key
            raise FileNotFoundError

        def query_value(_key: object, value_name: str) -> tuple[str, int]:
            if value_name == "SteamPath":
                return r"D:\PortableSteam", winreg.REG_SZ
            raise FileNotFoundError

        with (
            mock.patch.object(winreg, "OpenKey", side_effect=open_key),
            mock.patch.object(winreg, "QueryValueEx", side_effect=query_value),
        ):
            roots = patcher_gui._steam_roots()

        self.assertIn(Path(r"D:\PortableSteam"), roots)

    def test_linux_steam_roots_include_xdg_flatpak_and_snap(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary) / "HomeWithCase"
            xdg = Path(temporary) / "XDGData"
            with (
                mock.patch.object(patcher_gui.sys, "platform", "linux"),
                mock.patch.object(patcher_gui.Path, "home", return_value=home),
                mock.patch.dict(
                    patcher_gui.os.environ,
                    {
                        "XDG_DATA_HOME": str(xdg),
                        "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(
                            Path(temporary) / "CompatSteam"
                        ),
                    },
                    clear=True,
                ),
            ):
                roots = patcher_gui._steam_roots()

        self.assertIn(xdg / "Steam", roots)
        self.assertIn(Path(temporary) / "CompatSteam", roots)
        self.assertIn(home / ".steam" / "root", roots)
        self.assertIn(
            home
            / ".var"
            / "app"
            / "com.valvesoftware.Steam"
            / ".local"
            / "share"
            / "Steam",
            roots,
        )
        self.assertIn(
            home
            / "snap"
            / "steam"
            / "common"
            / ".local"
            / "share"
            / "Steam",
            roots,
        )

    def test_linux_path_keys_preserve_case(self) -> None:
        with mock.patch.object(patcher_gui.sys, "platform", "linux"):
            upper = patcher_gui._path_key(Path("Library") / "Steam")
            lower = patcher_gui._path_key(Path("library") / "steam")

        self.assertNotEqual(upper, lower)

    def test_linux_process_scanner_detects_proton_game_argument(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)
            process = proc / "4242"
            process.mkdir()
            (process / "comm").write_text("pressure-vessel\n", encoding="utf-8")
            (process / "cmdline").write_bytes(
                b"/usr/bin/wine64\0Z:\\steam\\ELDEN RING\\Game\\eldenring.exe\0"
            )
            uid = process.stat().st_uid
            with mock.patch.object(
                patcher_gui.os,
                "getuid",
                return_value=uid,
                create=True,
            ):
                blockers = patcher_gui._linux_running_blockers(proc)

        self.assertIn("Elden Ring", blockers)

    def test_linux_process_scanner_detects_unknown_eac_variant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            proc = Path(temporary)
            process = proc / "99"
            process.mkdir()
            (process / "comm").write_text(
                "easyanticheat_custom.exe\n", encoding="utf-8"
            )
            (process / "cmdline").write_bytes(b"easyanticheat_custom.exe\0")
            uid = process.stat().st_uid
            with mock.patch.object(
                patcher_gui.os,
                "getuid",
                return_value=uid,
                create=True,
            ):
                blockers = patcher_gui._linux_running_blockers(proc)

        self.assertEqual(blockers, ["Easy Anti-Cheat"])

    def test_linux_process_scanner_fails_closed_without_proc(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            mock.patch.object(
                patcher_gui.os,
                "getuid",
                return_value=0,
                create=True,
            ),
            self.assertRaisesRegex(patcher_gui.PatcherError, "consultar /proc"),
        ):
            patcher_gui._linux_running_blockers(Path(temporary) / "missing")

    def test_reads_and_requires_the_pinned_steam_build(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            steamapps = Path(temporary) / "steamapps"
            game = steamapps / "common" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"AppState"\n{\n  "installdir" "ELDEN RING"\n'
                '  "buildid"  "25080141"\n}\n',
                encoding="utf-8",
            )

            self.assertEqual(patcher_gui.steam_build_id(game), "25080141")
            with mock.patch.object(
                patcher_gui,
                "validate_game_archive_profile",
                return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
            ):
                compatibility = patcher_gui.require_supported_build(game)

            self.assertIn(
                patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
                compatibility,
            )
            self.assertIn("BuildID esperado 25080141", compatibility)
            self.assertIn("nao sao confirmados pelo manifesto", compatibility)

    def test_different_manifest_build_is_only_an_auxiliary_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            steamapps = Path(temporary) / "steamapps"
            game = steamapps / "common" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"installdir" "ELDEN RING"\n"buildid" "99999999"\n',
                encoding="utf-8",
            )

            with mock.patch.object(
                patcher_gui,
                "validate_game_archive_profile",
                return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
            ):
                result = patcher_gui.require_supported_build(game)

            self.assertIn("BuildID 99999999", result)
            self.assertIn("Steam/online nao confirmados", result)

    def test_copied_supported_manifest_cannot_override_wrong_game_files(self) -> None:
        info = patcher_gui.SteamBuildInfo("25080141", "identified")
        with (
            mock.patch.object(
                patcher_gui,
                "validate_game_archive_profile",
                side_effect=patcher_gui.CompatibilityError("sd.bhd divergente"),
            ),
            self.assertRaisesRegex(
                patcher_gui.GameFilesCompatibilityError,
                r"ERPT-FILES-001[\s\S]*Copiar um appmanifest",
            ) as raised,
        ):
            patcher_gui.require_supported_build(Path("old-game"), info)

        self.assertTrue(raised.exception.before_game_writes)

    def test_missing_manifest_uses_authenticated_local_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            game = (
                Path(temporary)
                / "steamapps"
                / "common"
                / "ELDEN RING"
                / "Game"
            )
            game.mkdir(parents=True)

            with mock.patch.object(patcher_gui, "_steam_roots", return_value=[]):
                info = patcher_gui.steam_build_info(game)

            self.assertIsNone(info.build_id)
            self.assertEqual(info.status, "manifest_missing")
            with mock.patch.object(
                patcher_gui,
                "validate_game_archive_profile",
                return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
            ):
                result = patcher_gui.require_supported_build(game, info)

            self.assertIn(patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id, result)
            self.assertIn("Steam/online nao confirmados", result)

    def test_uses_lexical_library_path_after_game_path_was_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            resolved_game = root / "physical" / "Game"
            resolved_game.mkdir(parents=True)
            lexical_game = (
                root
                / "SteamLibrary"
                / "steamapps"
                / "common"
                / "ELDEN RING"
                / "Game"
            )
            lexical_game.mkdir(parents=True)
            manifest = (
                root
                / "SteamLibrary"
                / "steamapps"
                / "appmanifest_1245620.acf"
            )
            manifest.write_text(
                '"installdir" "ELDEN RING"\n"buildid" "25080141"\n',
                encoding="utf-8",
            )

            with (
                mock.patch.object(patcher_gui, "_steam_roots", return_value=[]),
                mock.patch.object(
                    patcher_gui,
                    "_same_directory_identity",
                    side_effect=lambda left, right: (
                        left == lexical_game and right == resolved_game
                    ),
                ),
            ):
                info = patcher_gui.steam_build_info(
                    resolved_game,
                    game_path_hints=(lexical_game,),
                )

            self.assertEqual(info, patcher_gui.SteamBuildInfo("25080141", "identified"))

    def test_foreign_path_hint_cannot_authorize_another_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "selected" / "Game"
            game.mkdir(parents=True)
            foreign_game = (
                root
                / "SteamLibrary"
                / "steamapps"
                / "common"
                / "ELDEN RING"
                / "Game"
            )
            foreign_game.mkdir(parents=True)
            (foreign_game.parents[2] / "appmanifest_1245620.acf").write_text(
                '"installdir" "ELDEN RING"\n"buildid" "25080141"\n',
                encoding="utf-8",
            )

            with mock.patch.object(patcher_gui, "_steam_roots", return_value=[]):
                info = patcher_gui.steam_build_info(
                    game,
                    game_path_hints=(foreign_game,),
                )

            self.assertEqual(
                info,
                patcher_gui.SteamBuildInfo(None, "manifest_missing"),
            )

    def test_directory_identity_check_fails_closed_on_os_error(self) -> None:
        left = mock.Mock(spec=Path)
        right = mock.Mock(spec=Path)
        left.samefile.side_effect = OSError("identity unavailable")

        self.assertFalse(patcher_gui._same_directory_identity(left, right))

    def test_invalid_physical_manifest_does_not_hide_valid_lexical_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "physical" / "common" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            (root / "physical" / "appmanifest_1245620.acf").write_text(
                '"buildid" "99999999"\n',
                encoding="utf-8",
            )
            lexical_game = (
                root
                / "SteamLibrary"
                / "steamapps"
                / "common"
                / "ELDEN RING"
                / "Game"
            )
            lexical_game.mkdir(parents=True)
            (lexical_game.parents[2] / "appmanifest_1245620.acf").write_text(
                '"installdir" "ELDEN RING"\n"buildid" "25080141"\n',
                encoding="utf-8",
            )

            def same_identity(left: Path, right: Path) -> bool:
                return left == lexical_game and right == game

            with (
                mock.patch.object(patcher_gui, "_steam_roots", return_value=[]),
                mock.patch.object(
                    patcher_gui,
                    "_same_directory_identity",
                    side_effect=same_identity,
                ),
            ):
                info = patcher_gui.steam_build_info(
                    game,
                    game_path_hints=(lexical_game,),
                )

            self.assertEqual(
                info,
                patcher_gui.SteamBuildInfo("25080141", "identified"),
            )

    def test_finds_manifest_through_registered_library_for_same_game(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "physical" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            library = root / "SteamLibrary"
            steamapps = library / "steamapps"
            steamapps.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"installdir" "ELDEN RING"\n"buildid" "25080141"\n',
                encoding="utf-8",
            )

            with (
                mock.patch.object(
                    patcher_gui, "_steam_roots", return_value=[library]
                ),
                mock.patch.object(
                    patcher_gui,
                    "_steam_libraries",
                    return_value=[library],
                ),
                mock.patch.object(
                    patcher_gui, "_same_directory_identity", return_value=True
                ) as same_directory,
            ):
                info = patcher_gui.steam_build_info(game)

            self.assertEqual(info, patcher_gui.SteamBuildInfo("25080141", "identified"))
            same_directory.assert_called()

    def test_does_not_borrow_manifest_from_another_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / "copied" / "ELDEN RING" / "Game"
            game.mkdir(parents=True)
            library = root / "SteamLibrary"
            steamapps = library / "steamapps"
            steamapps.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"installdir" "ELDEN RING"\n"buildid" "25080141"\n',
                encoding="utf-8",
            )

            with (
                mock.patch.object(
                    patcher_gui, "_steam_roots", return_value=[library]
                ),
                mock.patch.object(
                    patcher_gui,
                    "_steam_libraries",
                    return_value=[library],
                ),
                mock.patch.object(
                    patcher_gui, "_same_directory_identity", return_value=False
                ),
            ):
                info = patcher_gui.steam_build_info(game)

            self.assertIsNone(info.build_id)
            self.assertEqual(info.status, "manifest_not_linked")

    def test_direct_manifest_must_name_the_selected_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            steamapps = Path(temporary) / "steamapps"
            selected = steamapps / "common" / "ELDEN RING COPY" / "Game"
            selected.mkdir(parents=True)
            (steamapps / "appmanifest_1245620.acf").write_text(
                '"installdir" "ELDEN RING"\n"buildid" "25080141"\n',
                encoding="utf-8",
            )

            with mock.patch.object(patcher_gui, "_steam_roots", return_value=[]):
                info = patcher_gui.steam_build_info(selected)

            self.assertEqual(
                info,
                patcher_gui.SteamBuildInfo(None, "manifest_not_linked"),
            )

    def test_install_worker_rejects_incompatible_files_before_creating_engine(self) -> None:
        app = mock.Mock()
        build_error = patcher_gui.GameFilesCompatibilityError(
            "sd.bhd divergente",
            before_game_writes=True,
        )
        app._validated_context.side_effect = build_error

        with mock.patch.object(patcher_gui, "PatchEngine") as engine_class:
            patcher_gui.PatcherApp._install_worker(app, "selected-game")

        engine_class.assert_not_called()
        app._report_failure.assert_called_once()
        self.assertIs(app._report_failure.call_args.kwargs["exc"], build_error)

    def test_install_worker_suspends_before_engine_or_payload_access(self) -> None:
        app = mock.Mock()
        app._validated_context.return_value = (Path("selected-game"), "25080141")

        with (
            mock.patch.object(patcher_gui, "INSTALLATION_SUSPENDED", True),
            mock.patch.object(patcher_gui, "PatchEngine") as engine_class,
            mock.patch.object(patcher_gui, "ensure_patch_data") as ensure_payload,
        ):
            patcher_gui.PatcherApp._install_worker(app, "selected-game")

        engine_class.assert_not_called()
        ensure_payload.assert_not_called()
        app._report_failure.assert_called_once()
        error = app._report_failure.call_args.kwargs["exc"]
        self.assertIsInstance(error, patcher_gui.InstallationSuspendedError)
        self.assertEqual(error.code, "ERPT-AUDIO-001")
        self.assertIn("Nenhum arquivo novo sera alterado", str(error))

    def test_install_worker_applies_payload_when_suspension_is_disabled(self) -> None:
        app = mock.Mock()
        app._diagnostic_lock = threading.Lock()
        game_dir = Path("selected-game")
        app._validated_context.return_value = (game_dir, "25080141")
        patch_engine = mock.Mock()
        patch_engine.load_archives.return_value = 42
        patch_engine.apply_plan.return_value = (2, 0)
        plan = mock.Mock()
        plan.matched_file_count = 2
        plan.payload_file_count = 2
        plan.match_ratio = 1.0
        plan.writes = (mock.Mock(), mock.Mock())
        plan.unmatched_files = ()

        with (
            mock.patch.object(patcher_gui, "INSTALLATION_SUSPENDED", False),
            mock.patch.object(
                patcher_gui, "PatchEngine", return_value=patch_engine
            ) as engine_class,
            mock.patch.object(
                patcher_gui, "ensure_patch_data", return_value=Path("payload")
            ) as ensure_payload,
            mock.patch.object(
                patcher_gui, "build_authenticated_plan", return_value=plan
            ) as build_plan,
        ):
            patcher_gui.PatcherApp._install_worker(app, "selected-game")

        engine_class.assert_called_once()
        self.assertEqual(engine_class.call_args.args, (game_dir,))
        self.assertIs(
            engine_class.call_args.kwargs["archive_profile"],
            patcher_gui.SUPPORTED_AUDIO_PROFILE,
        )
        patch_engine.load_archives.assert_called_once_with()
        ensure_payload.assert_called_once()
        build_plan.assert_called_once_with(
            patch_engine, Path("payload"), progress=app._progress
        )
        patch_engine.apply_plan.assert_called_once_with(
            plan,
            progress=app._progress,
            bhd_integrity_mode=patcher_gui.BHD_INTEGRITY_SCOPED_MOD,
        )
        app._report_failure.assert_not_called()
        app._set_stage.assert_any_call(
            "completed",
            "Dublagem instalada com seguranca.",
            write_state="committed",
            finished=True,
        )

    def test_suspension_code_is_preserved_in_diagnostic_state(self) -> None:
        app = self._diagnostic_state_stub()

        code, kind, _message = patcher_gui.PatcherApp._record_error(
            app, patcher_gui.InstallationSuspendedError()
        )

        self.assertEqual(code, "ERPT-AUDIO-001")
        self.assertEqual(kind, "InstallationSuspendedError")
        self.assertEqual(app._last_error_code, "ERPT-AUDIO-001")

    def test_restore_remains_available_while_installation_is_suspended(self) -> None:
        app = mock.Mock()
        game_dir = Path("selected-game")
        app._validated_context.return_value = (game_dir, "25080141")
        patch_engine = mock.Mock()

        with (
            mock.patch.object(patcher_gui, "INSTALLATION_SUSPENDED", True),
            mock.patch.object(
                patcher_gui, "PatchEngine", return_value=patch_engine
            ) as engine_class,
            mock.patch.object(patcher_gui, "ensure_patch_data") as ensure_payload,
        ):
            patcher_gui.PatcherApp._restore_worker(app, "selected-game")

        engine_class.assert_called_once()
        self.assertEqual(engine_class.call_args.args, (game_dir,))
        self.assertIs(
            engine_class.call_args.kwargs["archive_profile"],
            patcher_gui.SUPPORTED_AUDIO_PROFILE,
        )
        patch_engine.load_archives.assert_called_once_with()
        patch_engine.restore_current_backup.assert_called_once_with()
        ensure_payload.assert_not_called()
        app._report_failure.assert_not_called()
        app._set_stage.assert_any_call(
            "restore_completed",
            "Arquivos originais restaurados e verificados.",
            write_state="restored",
            finished=True,
        )

    def test_restore_failure_points_user_to_steam_verification(self) -> None:
        app = mock.Mock()
        app._validated_context.return_value = (Path("selected-game"), "25080141")
        patch_engine = mock.Mock()
        patch_engine.restore_current_backup.side_effect = patcher_gui.BackupError(
            "backup ausente; use a verificacao da Steam"
        )

        with mock.patch.object(
            patcher_gui, "PatchEngine", return_value=patch_engine
        ):
            patcher_gui.PatcherApp._restore_worker(app, "selected-game")

        app._report_failure.assert_called_once()
        error = app._report_failure.call_args.kwargs["exc"]
        self.assertIn("verificacao da Steam", str(error))

    def test_precommit_file_change_does_not_claim_no_files_changed(self) -> None:
        error = patcher_gui.GameFilesCompatibilityError(
            "sd.bhd mudou",
            before_game_writes=False,
        )

        self.assertNotIn("Nenhum arquivo foi alterado", str(error))
        self.assertIn("revalidacao final", str(error))

    def test_precommit_revalidates_files_without_trusting_manifest(self) -> None:
        game_dir = Path("selected-game")
        info = patcher_gui.SteamBuildInfo("25080141", "identified")

        with (
            mock.patch.object(patcher_gui, "running_blockers", return_value=[]),
            mock.patch.object(
                patcher_gui,
                "steam_build_info",
                return_value=info,
            ),
            mock.patch.object(patcher_gui, "require_supported_build") as require,
            mock.patch.object(
                patcher_gui,
                "optional_movie_payload_present",
                return_value=False,
            ),
        ):
            patcher_gui.PatcherApp._precommit_guard(
                game_dir,
                selected_path=game_dir,
            )

        require.assert_called_once_with(
            game_dir,
            info,
            before_game_writes=False,
        )

    def test_precommit_accepts_missing_or_divergent_optional_manifest(self) -> None:
        game_dir = Path("selected-game")
        build_infos = (
            patcher_gui.SteamBuildInfo(None, "manifest_missing"),
            patcher_gui.SteamBuildInfo("99999999", "identified"),
        )

        for info in build_infos:
            with self.subTest(info=info):
                with (
                    mock.patch.object(
                        patcher_gui, "running_blockers", return_value=[]
                    ),
                    mock.patch.object(
                        patcher_gui,
                        "steam_build_info",
                        return_value=info,
                    ),
                    mock.patch.object(
                        patcher_gui,
                        "validate_game_archive_profile",
                        return_value=patcher_gui.SUPPORTED_AUDIO_PROFILE.profile_id,
                    ),
                    mock.patch.object(
                        patcher_gui,
                        "optional_movie_payload_present",
                        return_value=False,
                    ),
                ):
                    patcher_gui.PatcherApp._precommit_guard(game_dir)

    def test_precommit_still_rejects_wrong_real_files(self) -> None:
        game_dir = Path("selected-game")
        info = patcher_gui.SteamBuildInfo(None, "manifest_missing")

        with (
            mock.patch.object(patcher_gui, "running_blockers", return_value=[]),
            mock.patch.object(
                patcher_gui,
                "steam_build_info",
                return_value=info,
            ),
            mock.patch.object(
                patcher_gui,
                "validate_game_archive_profile",
                side_effect=patcher_gui.CompatibilityError("sd.bhd divergente"),
            ),
            mock.patch.object(
                patcher_gui,
                "optional_movie_payload_present",
                return_value=False,
            ),
            self.assertRaises(patcher_gui.GameFilesCompatibilityError) as raised,
        ):
            patcher_gui.PatcherApp._precommit_guard(game_dir)

        self.assertFalse(raised.exception.before_game_writes)
        self.assertIn("sd.bhd divergente", str(raised.exception))

    def test_error_freezes_stage_elapsed_time_for_later_report(self) -> None:
        app = self._diagnostic_state_stub()
        with mock.patch.object(
            patcher_gui.time, "monotonic", return_value=15.9
        ):
            patcher_gui.PatcherApp._record_error(app, ValueError("falha"))

        with mock.patch.object(
            patcher_gui,
            "build_diagnostic_report",
            return_value="{}\n",
        ) as build_report:
            patcher_gui.PatcherApp._diagnostic_report(app, "")

        self.assertEqual(
            build_report.call_args.kwargs["stage_elapsed_seconds"], 5
        )

    def test_manual_report_does_not_reread_manifest_or_reuse_another_path(self) -> None:
        app = self._diagnostic_state_stub()
        app._last_error_code = "ERPT-INSTALL-001"
        app._detected_build_path_key = patcher_gui.PatcherApp._diagnostic_path_key(
            "original-game"
        )
        with mock.patch.object(
            patcher_gui,
            "steam_build_info",
        ) as read_manifest:
            snapshot = patcher_gui.PatcherApp._diagnostic_snapshot(app, "other-game")

        read_manifest.assert_not_called()
        self.assertIsNone(snapshot["detected_build_id"])
        self.assertEqual(snapshot["build_status"], "not_checked")

    def test_manual_report_keeps_build_already_read_for_the_same_path(self) -> None:
        app = self._diagnostic_state_stub()
        app._detected_build_path_key = patcher_gui.PatcherApp._diagnostic_path_key(
            "selected-game"
        )

        snapshot = patcher_gui.PatcherApp._diagnostic_snapshot(
            app, r".\selected-game"
        )

        self.assertEqual(snapshot["detected_build_id"], "11111111")
        self.assertEqual(snapshot["build_status"], "identified")

    def test_failure_schedules_dialog_before_collecting_diagnostic(self) -> None:
        app = self._diagnostic_state_stub()
        app._status = mock.Mock()
        app._log = mock.Mock()
        scheduled: list[object] = []
        app._ui = scheduled.append

        with mock.patch.object(patcher_gui, "build_diagnostic_report") as build:
            patcher_gui.PatcherApp._report_failure(
                app,
                title="Falha",
                exc=ValueError("erro"),
                selected_path="",
                status_message="Cancelada",
            )

        build.assert_not_called()
        self.assertEqual(len(scheduled), 1)
        with app._diagnostic_lock:
            app._diagnostic_stage = "new_attempt"
            app._last_error_code = None
            app._detected_build_id = "22222222"
        app._show_failure_dialog = mock.Mock()
        scheduled[0]()  # type: ignore[operator]
        snapshot = app._show_failure_dialog.call_args.args[2]
        self.assertEqual(snapshot["stage"], "steam_build")
        self.assertEqual(snapshot["error_code"], "ERPT-DATA-001")
        self.assertEqual(snapshot["detected_build_id"], "11111111")

    def test_diagnostic_button_remains_available_while_install_is_busy(self) -> None:
        app = object.__new__(patcher_gui.PatcherApp)
        app._busy = False
        app.install_button = mock.Mock()
        app.restore_button = mock.Mock()
        app.browse_button = mock.Mock()
        app.path_entry = mock.Mock()
        app.report_button = mock.Mock()

        patcher_gui.PatcherApp._set_busy(app, True)

        self.assertTrue(app._busy)
        app.report_button.configure.assert_not_called()

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

    def test_process_detection_includes_easy_anticheat_eos(self) -> None:
        result = mock.Mock(
            returncode=0,
            stdout='"EasyAntiCheat_EOS.exe","123","Console","1","10.000 K"\n',
        )
        with (
            mock.patch.object(patcher_gui.sys, "platform", "win32"),
            mock.patch.dict(patcher_gui.os.environ, {"SystemRoot": r"C:\\Windows"}),
            mock.patch.object(patcher_gui.Path, "is_file", return_value=True),
            mock.patch.object(patcher_gui.subprocess, "run", return_value=result),
        ):
            self.assertEqual(
                patcher_gui.running_blockers(),
                ["Easy Anti-Cheat EOS"],
            )


if __name__ == "__main__":
    unittest.main()
