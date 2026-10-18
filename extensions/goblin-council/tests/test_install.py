"""Installation must preserve existing skill registrations and configuration."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("goblin_install", Path(__file__).resolve().parents[1] / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def test_roundtrip_idempotent_and_space_paths(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "skills with spaces"
            installer.install(dest)
            installer.install(dest)
            for name in installer.NAMES:
                self.assertTrue((dest / name / "SKILL.md").is_file())
            installer.install(dest, uninstall=True)
            self.assertEqual(list(dest.iterdir()), [])
            installer.install(dest, uninstall=True)

    def test_dry_run_does_not_create_destination(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "absent"
            installer.install(dest, dry_run=True)
            self.assertFalse(dest.exists())

    def test_collision_preflight_preserves_everything(self):
        for kind in ("directory", "file", "broken-link"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as root:
                dest = Path(root)
                collision = dest / "goblin-max"
                if kind == "directory": collision.mkdir()
                elif kind == "file": collision.write_text("user data")
                else: collision.symlink_to(dest / "absent")
                for uninstall in (False, True):
                    with self.assertRaises(ValueError):
                        installer.install(dest, uninstall=uninstall)
                self.assertFalse((dest / "goblin").exists())
                self.assertTrue(collision.exists() or collision.is_symlink())

    def test_partial_install_failure_removes_only_new_links(self):
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root)
            original = Path.symlink_to
            def fail_second(target, *args, **kwargs):
                if target.name == "goblin-max": raise OSError("fixture failure")
                return original(target, *args, **kwargs)
            with patch.object(Path, "symlink_to", fail_second):
                with self.assertRaises(OSError): installer.install(dest)
            self.assertEqual(list(dest.iterdir()), [])
