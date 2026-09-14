from __future__ import annotations

import json
import hashlib
import os
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from support.scripts import deploy_package, diablo_launch, mister_launcher, package_release


class PackageReleaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "source").mkdir()
        for name, content in (("engine.bin", b"engine"), ("core.rbf", b"rbf"), ("abi.hex", b"abi"),
                              ("launcher.py", b"launcher")):
            (self.root / "source" / name).write_bytes(content)
        (self.root / "assets" / "ui_art").mkdir(parents=True)
        (self.root / "assets" / "ui_art" / "diablo.pal").write_bytes(b"palette")
        (self.root / "source" / "unlisted.bin").write_bytes(b"unlisted")
        artifact_records = [
            {"path": "source/engine.bin", "sha256": hashlib.sha256(b"engine").hexdigest()},
            {"path": "source/core.rbf", "sha256": hashlib.sha256(b"rbf").hexdigest()},
            {"path": "source/abi.hex", "sha256": hashlib.sha256(b"abi").hexdigest()},
            {"path": "source/launcher.py", "sha256": hashlib.sha256(b"launcher").hexdigest()},
            {"path": "assets/ui_art/diablo.pal", "sha256": hashlib.sha256(b"palette").hexdigest()},
        ]
        self.candidate = self.root / "candidate.json"
        self.candidate.write_text(json.dumps({
            "schema": "diablo-candidate-manifest-v1",
            "status": "pass",
            "candidate_id": "a" * 64,
            "source_id": "b" * 64,
            "artifacts": artifact_records,
        }) + "\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create(self, name: str = "package", board: str = "de10-nano-test", **kwargs: str) -> Path:
        output = self.root / name
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            result = package_release.create_package(
                self.root,
                self.candidate,
                (("engine", "source/engine.bin"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                 ("launcher", "source/launcher.py")),
                board,
                output,
                "assets",
                **kwargs,
            )
        self.assertEqual(str(output.resolve()), result["package"])
        return output

    def test_create_and_verify_runtime_only_package(self) -> None:
        package = self.create()
        self.assertEqual([], package_release.verify_package(package, "de10-nano-test"))
        self.assertEqual("a" * 64, mister_launcher.verify_package(package)["candidate_id"])
        self.assertEqual(
            {"devilutionx", "Diablo.rbf", "transport_abi.hex", "diablo_launcher.py", "deployment.json",
             "package-manifest.json", "NOTICE.txt", "SETUP.md", "Diablo.sh", "Hellfire.sh",
             "LICENSE.fpga", "LICENSE.engine.md", "licenses", "assets"},
            {path.name for path in package.iterdir()},
        )
        self.assertIn("licensed Diablo and", (package / "NOTICE.txt").read_text(encoding="utf-8"))
        self.assertIn("update is interrupted", (package / "SETUP.md").read_text(encoding="utf-8"))
        for name, source in package_release.PACKAGE_LICENSE_SOURCES.items():
            self.assertEqual(source.read_bytes(), (package / name).read_bytes())
        for source in package_release.THIRD_PARTY_NOTICES.rglob("*"):
            if source.is_file():
                self.assertEqual(source.read_bytes(),
                                 (package / "licenses" / source.relative_to(package_release.THIRD_PARTY_NOTICES)).read_bytes())

    def test_launcher_verification_hashes_each_installed_file_once(self) -> None:
        package = self.create()
        expected = len(mister_launcher._file_records(package)) - 1  # package-manifest.json is excluded
        with mock.patch.object(mister_launcher, "sha256_file",
                               wraps=mister_launcher.sha256_file) as hash_file:
            mister_launcher.verify_package(package)
        self.assertEqual(expected, hash_file.call_count)

    def test_managed_launch_checks_entrypoints_without_walking_assets(self) -> None:
        package = self.create(board="de10-nano-mister")
        target = self.root / "target"
        state = deploy_package.install_package(package, target, "de10-nano-mister")
        release = target / state["active_release"]
        with mock.patch.object(mister_launcher, "MISTER_INSTALL_STATE", target / ".diablo-install.json"):
            with mock.patch.object(Path, "rglob", side_effect=AssertionError("repeated tree walk")):
                identity = mister_launcher._managed_package_identity(release)
                self.assertIsNotNone(identity)
                self.assertEqual(identity["candidate_id"], state["active_candidate_id"])
            with mock.patch.dict(os.environ, {"DIABLO_MISTER_VERIFY_FULL": "1"}):
                self.assertIsNone(mister_launcher._managed_package_identity(release))
            (release / "devilutionx").write_bytes(b"wrong size")
            self.assertIsNone(mister_launcher._managed_package_identity(release))

    def test_full_verification_rejects_directory_symlinks(self) -> None:
        package = self.create()
        try:
            (package / "linked").symlink_to(self.root / "assets", target_is_directory=True)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaisesRegex(mister_launcher.LaunchError, "symlink"):
            mister_launcher.verify_package(package)

    def test_bundled_hellfire_mod_is_packaged_and_staged(self) -> None:
        mod = self.root / "source" / "hf"
        (mod / "lua/mods/hf").mkdir(parents=True)
        (mod / "manifest.ini").write_text("[mod]\nname=Hellfire\n", encoding="utf-8")
        (mod / "lua/mods/hf/init.lua").write_text("hellfire.enable()\n", encoding="utf-8")
        candidate = json.loads(self.candidate.read_text(encoding="utf-8"))
        packed = self.root / "assets/mods/hf.mpq"
        packed.parent.mkdir(parents=True)
        packed.write_bytes(b"packed-hf-fixture")
        candidate["artifacts"].append({"path": "assets/mods/hf.mpq",
                                       "sha256": hashlib.sha256(packed.read_bytes()).hexdigest()})
        for path in sorted(mod.rglob("*")):
            if path.is_file():
                candidate["artifacts"].append({
                    "path": path.relative_to(self.root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                })
        self.candidate.write_text(json.dumps(candidate) + "\n", encoding="utf-8")

        package = self.create("hellfire-package", hellfire_mod="source/hf")
        self.assertEqual([], package_release.verify_package(package, "de10-nano-test"))
        self.assertTrue((package / "assets/mods/hf/manifest.ini").is_file())
        save_root = self.root / "save-root"
        save_root.mkdir()
        legacy = save_root / "mods/hf/lua/mods/hf/init.lua"
        legacy.parent.mkdir(parents=True)
        legacy.write_text("hellfire.enable()\n", encoding="utf-8")
        hero = save_root / "single_0.sv"
        hero.write_bytes(b"existing hero")
        mister_launcher._stage_hellfire_mod(package, save_root)
        staged = save_root / "mods/hf.mpq"
        self.assertEqual(b"packed-hf-fixture", staged.read_bytes())
        self.assertFalse((save_root / "mods/hf").exists())
        backup = save_root.parent / "save-root.legacy-hf/lua/mods/hf/init.lua"
        self.assertEqual("hellfire.enable()\n", backup.read_text(encoding="utf-8"))
        self.assertEqual(b"existing hero", hero.read_bytes())
        mister_launcher._stage_hellfire_mod(package, save_root)
        staged.write_bytes(b"user change")
        with self.assertRaisesRegex(mister_launcher.LaunchError, "differs from package"):
            mister_launcher._stage_hellfire_mod(package, save_root)

    def test_changed_legacy_mod_is_preserved_and_migration_stops(self) -> None:
        package = self.root / "mod-package"
        bundled = package / "assets/mods/hf/lua/mods/hf/init.lua"
        bundled.parent.mkdir(parents=True)
        bundled.write_bytes(b"original")
        (package / "assets/mods/hf.mpq").write_bytes(b"packed")
        save_root = self.root / "save-root"
        legacy = save_root / "mods/hf/lua/mods/hf/init.lua"
        legacy.parent.mkdir(parents=True)
        legacy.write_bytes(b"user modification")
        with self.assertRaisesRegex(mister_launcher.LaunchError, "differs from package"):
            mister_launcher._stage_hellfire_mod(package, save_root)
        self.assertEqual(b"user modification", legacy.read_bytes())
        self.assertFalse((save_root / "mods/hf.mpq").exists())
        self.assertFalse((save_root.parent / "save-root.legacy-hf").exists())

    def test_packed_mod_exception_does_not_admit_game_archives(self) -> None:
        for name in ("DIABDAT.MPQ", "mods/other.mpq", "mods/hf.mpq/secret.mpq"):
            with self.subTest(name=name):
                source = self.root / "assets" / name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_bytes(b"must not ship")
                with self.assertRaisesRegex(ValueError, "private-looking"):
                    package_release._safe_asset_source(self.root, "assets")
                source.unlink()

    def run_menu(self, package: Path, campaign: str, target: Path, arguments: tuple[str, ...] = ()) -> list[str]:
        entry = package / ("Diablo.sh" if campaign == "diablo" else "Hellfire.sh")
        text = entry.read_text(encoding="utf-8")
        code = text.split("<<'DIABLO_MENU_PY'\n", 1)[1].rsplit("DIABLO_MENU_PY", 1)[0]
        with mock.patch.dict(os.environ, {"DIABLO_INSTALL_ROOT": str(target)}, clear=True), \
                mock.patch("sys.argv", ["diablo-menu", *arguments]), mock.patch("os.execv") as execute:
            exec(compile(code, str(entry), "exec"), {})
        return execute.call_args.args[1]

    def test_menu_entries_resolve_active_install_and_both_campaigns(self) -> None:
        package = self.create()
        target = self.root / "target with spaces"
        state = deploy_package.install_package(package, target, "de10-nano-test")
        for campaign in ("diablo", "hellfire"):
            command = self.run_menu(package, campaign, target)
            self.assertEqual(str(target / state["active_release"] / "diablo_launcher.py"), command[1])
            self.assertEqual(campaign, command[command.index("--campaign") + 1])
            self.assertEqual(str(target / "games/Diablo"), command[command.index("--data-root") + 1])
            self.assertEqual(str(target / "saves/Diablo"), command[command.index("--save-root") + 1])
            self.assertEqual(str(target / "config/Diablo"), command[command.index("--config-root") + 1])
        self.assertEqual(["--duration", "30"], self.run_menu(package, "diablo", target, ("--duration", "30"))[-2:])

    def test_menu_rejects_missing_activation_and_changed_launcher(self) -> None:
        package = self.create()
        target = self.root / "target"
        with self.assertRaises(SystemExit):
            self.run_menu(package, "diablo", target)
        state = deploy_package.install_package(package, target, "de10-nano-test")
        (target / state["active_release"] / "diablo_launcher.py").write_text("changed", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_menu(package, "diablo", target)

    @unittest.skipUnless(os.name == "posix", "target menu requires POSIX exec process replacement")
    def test_menu_bootstrap_executes_verified_launcher(self) -> None:
        launcher = self.root / "source/launcher.py"
        launcher.write_bytes(b"import json, sys\nprint(json.dumps(sys.argv))\n")
        candidate = json.loads(self.candidate.read_text(encoding="utf-8"))
        for record in candidate["artifacts"]:
            if record["path"] == "source/launcher.py":
                record["sha256"] = hashlib.sha256(launcher.read_bytes()).hexdigest()
        self.candidate.write_text(json.dumps(candidate), encoding="utf-8")
        package = self.create()
        target = self.root / "target with spaces"
        state = deploy_package.install_package(package, target, "de10-nano-test")
        result = subprocess.run(["sh", str(package / "Hellfire.sh"), "--duration", "1"],
                                env={**os.environ, "DIABLO_INSTALL_ROOT": str(target)},
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(0, result.returncode, result.stderr)
        command = json.loads(result.stdout)
        self.assertEqual(str(target / state["active_release"] / "diablo_launcher.py"), command[0])
        self.assertEqual("hellfire", command[command.index("--campaign") + 1])
        self.assertEqual(["--duration", "1"], command[-2:])

    def test_existing_menu_copy_follows_update_and_rollback(self) -> None:
        package = self.create()
        target = self.root / "target"
        first = deploy_package.install_package(package, target, "de10-nano-test")
        candidate = json.loads(self.candidate.read_text(encoding="utf-8"))
        candidate["candidate_id"] = "c" * 64
        self.candidate.write_text(json.dumps(candidate), encoding="utf-8")
        updated = self.create("updated")
        second = deploy_package.install_package(updated, target, "de10-nano-test")
        self.assertNotEqual(first["active_release"], second["active_release"])
        self.assertEqual(str(target / second["active_release"] / "diablo_launcher.py"),
                         self.run_menu(package, "diablo", target)[1])
        deploy_package.rollback_installation(target, "de10-nano-test")
        self.assertEqual(str(target / first["active_release"] / "diablo_launcher.py"),
                         self.run_menu(package, "diablo", target)[1])

    def test_changed_dependency_notice_is_rejected(self) -> None:
        package = self.create()
        notice = next(path for path in (package / "licenses").rglob("*") if path.is_file())
        notice.write_bytes(notice.read_bytes() + b"changed")
        self.assertTrue(package_release.verify_package(package))
        with self.assertRaises(mister_launcher.LaunchError):
            mister_launcher.verify_package(package)

    def test_menu_rejects_release_path_escape(self) -> None:
        package = self.create()
        target = self.root / "target"
        state = deploy_package.install_package(package, target, "de10-nano-test")
        state["active_release"] = "../outside"
        (target / deploy_package.STATE_FILENAME).write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.run_menu(package, "diablo", target)

    def test_clean_package_supports_launcher_preflight(self) -> None:
        package = self.create()
        data = self.root / "data"
        data.mkdir()
        (data / "DIABDAT.MPQ").write_bytes(b"supplied privately")
        boot = self.root / "boot-id"
        boot.write_text("12345678-1234-1234-1234-123456789abc\n", encoding="utf-8")
        context = diablo_launch.preflight(
            package,
            None,
            package / "Diablo.rbf",
            package / "devilutionx",
            "diablo",
            data,
            self.root / "saves",
            self.root / "runtime",
            boot,
            "0x3fe00000",
            Path("transport.lock"),
            package / "deployment.json",
            "de10-nano-test",
        )
        self.assertEqual("a" * 64, context.candidate_id)
        self.assertEqual("b" * 64, context.source_id)

    def test_timedemo_requests_bounded_target_frame_pacing(self) -> None:
        self.assertTrue(mister_launcher._force_frame_pacing(["--spawn", "--timedemo"]))
        self.assertTrue(mister_launcher._force_frame_pacing(["--spawn", "--demo", "0"]))
        self.assertTrue(mister_launcher._force_frame_pacing([]))

    def test_mutation_and_private_file_are_rejected(self) -> None:
        package = self.create()
        (package / "Diablo.rbf").write_bytes(b"changed")
        problems = package_release.verify_package(package, "de10-nano-test")
        self.assertTrue(any("hash" in problem for problem in problems), problems)
        (package / "private.sav").write_bytes(b"private")
        problems = package_release.verify_package(package, "de10-nano-test")
        self.assertTrue(any("unexpected files" in problem for problem in problems), problems)
        self.assertTrue(any("private-data" in problem for problem in problems), problems)

    def test_existing_output_is_never_overwritten(self) -> None:
        package = self.create()
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            with self.assertRaises(ValueError):
                package_release.create_package(
                    self.root,
                    self.candidate,
                    (("engine", "source/engine.bin"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                     ("launcher", "source/launcher.py")),
                    "de10-nano-test",
                    package,
                    "assets",
                )

    def test_non_candidate_or_private_source_cannot_be_packaged(self) -> None:
        private = self.root / "game"
        private.mkdir()
        (private / "secret.mpq").write_bytes(b"private")
        with mock.patch.object(package_release.candidate_manifest, "verify_manifest", return_value=[]):
            with self.assertRaises(ValueError):
                package_release.create_package(
                    self.root,
                    self.candidate,
                    (("engine", "game/secret.mpq"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                     ("launcher", "source/launcher.py")),
                    "de10-nano-test",
                    self.root / "private-package",
                    "assets",
                )
            with self.assertRaises(ValueError):
                package_release.create_package(
                    self.root,
                    self.candidate,
                    (("engine", "source/unlisted.bin"), ("rbf", "source/core.rbf"), ("abi", "source/abi.hex"),
                     ("launcher", "source/launcher.py")),
                    "de10-nano-test",
                    self.root / "mismatched-package",
                    "assets",
                )


if __name__ == "__main__":
    unittest.main()
