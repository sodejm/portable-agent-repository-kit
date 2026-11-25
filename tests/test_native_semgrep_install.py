"""Exercise offline native extraction with synthetic, never-executed wheel bytes."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import struct
import subprocess
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "native_install", ROOT / "tools/push_gate/install_native_semgrep.py"
)
INSTALL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALL)


def elf(needed=(), cpu=62):
    """Build a minimal ELF64 dependency table, not an executable program."""
    strings = b"\0"
    positions = []
    for name in needed:
        positions.append(len(strings))
        strings += name.encode() + b"\0"
    body = bytearray(512 + len(strings))
    body[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", body, 18, cpu)
    struct.pack_into("<Q", body, 32, 64)
    struct.pack_into("<HH", body, 54, 56, 2)
    struct.pack_into("<IIQQQQQQ", body, 64, 1, 0, 0, 4096, 0, len(body), len(body), 8)
    dynamic = [(1, position) for position in positions] + [
        (5, 4608),
        (10, len(strings)),
        (0, 0),
    ]
    struct.pack_into(
        "<IIQQQQQQ", body, 120, 2, 0, 176, 4272, 0, len(dynamic) * 16, 0, 8
    )
    for index, (tag, value) in enumerate(dynamic):
        struct.pack_into("<QQ", body, 176 + index * 16, tag, value)
    body[512:] = strings
    return bytes(body)


def macho(needed=()):
    """Build thin ARM64 Mach-O load commands without executable instructions."""
    commands = []
    for name in needed:
        text = name.encode() + b"\0"
        length = (24 + len(text) + 7) // 8 * 8
        commands.append(
            struct.pack("<IIIIII", 12, length, 24, 0, 0, 0)
            + text
            + b"\0" * (length - 24 - len(text))
        )
    payload = b"".join(commands)
    return (
        struct.pack(
            "<IIIIIIII", 0xFEEDFACF, 0x0100000C, 0, 2, len(commands), len(payload), 0, 0
        )
        + payload
    )


class NativeInstallTests(unittest.TestCase):
    """Verify extraction policy and atomic publication independently of real wheels."""

    def setUp(self):
        """Keep every synthetic wheel and installation in a disposable directory."""
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.wheel = self.root / "synthetic.whl"

    def wheel_bytes(self, members):
        """Write ordered ZIP members and return the fixture's own digest."""
        with warnings.catch_warnings(), zipfile.ZipFile(self.wheel, "w") as archive:
            warnings.simplefilter("ignore", UserWarning)
            for name, content in members:
                archive.writestr(name, content)
        return hashlib.sha256(self.wheel.read_bytes()).hexdigest()

    def test_official_digests_and_documented_platforms(self):
        """Keep all supplied artifact identities synchronized with the guide."""
        self.assertEqual(INSTALL.VERSION, "1.187.0")
        self.assertEqual(
            INSTALL.WHEELS,
            {
                "macos-arm64": "a44a8f486719e69fe38c451c70b4808bed5532bbcb4c25a8dd04a74617dfcca0",
                "linux-aarch64": "79f0a3dc63607fada4ae2225599ab5eef8005124a8484814184df72805afcfc0",
                "linux-x86_64": "ad160ed527bd153b96616814366a6d17f451d37babf75df6705327aede0cc8bd",
            },
        )
        guide = (ROOT / "docs/LOCAL_PUSH_GATE.md").read_text()
        for digest in INSTALL.WHEELS.values():
            self.assertIn(digest, guide)

    def test_platform_allowlist(self):
        """Reject translated macOS, Windows, musl and older glibc hosts."""
        cases = [
            ("darwin", "arm64", ("", ""), "macos-arm64"),
            ("linux", "x86_64", ("glibc", "2.34"), "linux-x86_64"),
            ("linux", "aarch64", ("glibc", "2.40"), "linux-aarch64"),
            ("darwin", "x86_64", ("", ""), None),
            ("win32", "ARM64", ("", ""), None),
            ("linux", "aarch64", ("musl", "1.2"), None),
            ("linux", "x86_64", ("glibc", "2.33"), None),
            ("linux", "x86_64", ("glibc", "invalid"), None),
        ]
        for host, machine, libc, expected in cases:
            with (
                self.subTest(host=host, machine=machine, libc=libc),
                patch.object(INSTALL.sys, "platform", host),
                patch.object(INSTALL.platform, "machine", return_value=machine),
                patch.object(INSTALL.platform, "libc_ver", return_value=libc),
            ):
                if expected:
                    self.assertEqual(INSTALL.host_platform(), expected)
                else:
                    with self.assertRaises(INSTALL.InstallError):
                        INSTALL.host_platform()

    def test_digest_before_zip_parsing(self):
        """Unverified bytes never reach archive parsing or payload execution."""
        self.wheel.write_bytes(b"not a ZIP archive")
        with patch.object(INSTALL.zipfile, "ZipFile") as parser:
            with self.assertRaisesRegex(INSTALL.InstallError, "SHA256"):
                INSTALL.native_payload(self.wheel, "0" * 64, "linux-x86_64")
            parser.assert_not_called()

    def test_dependency_closure_excludes_python_and_unused_libraries(self):
        """Preserve linked library paths and exclude every unused distribution member."""
        for target, engine, library in (
            ("linux-x86_64", elf(["libfixture.so", "libc.so.6"]), elf()),
            ("linux-aarch64", elf(["libfixture.so"], 183), elf(cpu=183)),
            (
                "macos-arm64",
                macho(["@rpath/libfixture.so", "/usr/lib/libSystem.B.dylib"]),
                macho(),
            ),
        ):
            with self.subTest(target=target):
                digest = self.wheel_bytes(
                    [
                        (INSTALL.ENGINE, engine),
                        ("semgrep.libs/libfixture.so", library),
                        ("semgrep/bin/unused.so", b"must not even parse"),
                        ("semgrep/main.py", b"raise RuntimeError('must not execute')"),
                        ("mcp/__init__.py", b"must not install"),
                        ("semgrep-1.187.0.dist-info/METADATA", b"Requires-Dist: mcp"),
                    ]
                )
                self.assertEqual(
                    INSTALL.native_payload(self.wheel, digest, target),
                    {
                        INSTALL.ENGINE: engine,
                        "semgrep.libs/libfixture.so": library,
                    },
                )

    def test_wheel_purelib_installation_path(self):
        """Wheel purelib members install alongside the wheel's top-level packages."""
        engine = elf(["libfixture.so"])
        library = elf()
        members = [
            (f"semgrep-{INSTALL.VERSION}.data/purelib/{INSTALL.ENGINE}", engine),
            ("semgrep.libs/libfixture.so", library),
        ]
        digest = self.wheel_bytes(members)
        self.assertEqual(
            INSTALL.native_payload(self.wheel, digest, "linux-x86_64"),
            {INSTALL.ENGINE: engine, "semgrep.libs/libfixture.so": library},
        )

    def test_elf_dependency_names_in_separate_load_segments(self):
        """Resolve each linked name within its mapping in a split dynamic string table."""
        binary = bytearray(elf(["one.so", "two.so"]))
        # Make room for a third program header by relocating the dynamic records.
        binary[288:368] = binary[176:256]
        struct.pack_into("<H", binary, 56, 3)
        struct.pack_into("<Q", binary, 120 + 8, 288)
        boundary = 512 + len(b"\0one.so\0")
        struct.pack_into("<QQ", binary, 64 + 32, boundary, boundary)
        size = len(binary) - boundary
        struct.pack_into(
            "<IIQQQQQQ", binary, 176, 1, 0, boundary, 4096 + boundary, 0, size, size, 8
        )
        self.assertEqual(
            INSTALL.dependencies(bytes(binary), "linux-x86_64"), ["one.so", "two.so"]
        )

    def test_unsafe_zip_members_rejected_even_when_unused(self):
        """Traversal, aliases, duplicate paths and symlinks cannot enter staging."""
        link = zipfile.ZipInfo("discarded-link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        for name in (
            "../escape",
            "/absolute",
            "semgrep/../escape",
            "a//b",
            "a/./b",
            "a\\b",
            "C:drive",
            "line\nbreak",
            INSTALL.ENGINE,
            f"semgrep-{INSTALL.VERSION}.data/purelib/{INSTALL.ENGINE}",
            link,
        ):
            with self.subTest(name=str(name)):
                digest = self.wheel_bytes([(INSTALL.ENGINE, elf()), (name, b"unsafe")])
                with self.assertRaises(INSTALL.InstallError):
                    INSTALL.native_payload(self.wheel, digest, "linux-x86_64")

    def test_missing_ambiguous_malformed_and_wrong_architecture_fail(self):
        """No dependency lookup may silently fall back to an unbundled library."""
        cases = [
            [(INSTALL.ENGINE, elf(["missing.so"]))],
            [
                (INSTALL.ENGINE, elf(["duplicate.so"])),
                ("semgrep/bin/duplicate.so", elf()),
                ("semgrep.libs/duplicate.so", elf()),
            ],
            [(INSTALL.ENGINE, elf(cpu=183))],
            [(INSTALL.ENGINE, b"truncated")],
        ]
        for members in cases:
            with self.subTest(members=len(members)):
                digest = self.wheel_bytes(members)
                with self.assertRaises((INSTALL.InstallError, struct.error)):
                    INSTALL.native_payload(self.wheel, digest, "linux-x86_64")

    def test_publish_native_identity_manifest_and_no_python(self):
        """Both native names share an inode and a deterministic payload manifest."""
        digest = self.wheel_bytes(
            [(INSTALL.ENGINE, elf()), ("semgrep/main.py", b"discard")]
        )
        destination = self.root / "new-native"
        result = subprocess.CompletedProcess(
            [], 0, b"semgrep-core version: 1.187.0 (a5341ae595)\n", b""
        )
        with (
            patch.object(INSTALL, "host_platform", return_value="linux-x86_64"),
            patch.dict(INSTALL.WHEELS, {"linux-x86_64": digest}),
            patch.object(INSTALL.subprocess, "run", return_value=result) as run,
        ):
            INSTALL.install(self.wheel, destination)
        engine = destination / INSTALL.ENGINE
        alias = engine.with_name("osemgrep")
        self.assertEqual(engine.stat().st_ino, alias.stat().st_ino)
        self.assertEqual(stat.S_IMODE(engine.stat().st_mode), 0o755)
        self.assertEqual(
            {
                p.relative_to(destination).as_posix()
                for p in destination.rglob("*")
                if p.is_file()
            },
            {INSTALL.ENGINE, "semgrep/bin/osemgrep", "native-install.json"},
        )
        manifest = json.loads((destination / "native-install.json").read_text())
        self.assertEqual(manifest["wheel_sha256"], digest)
        self.assertEqual(
            manifest["files"][INSTALL.ENGINE], hashlib.sha256(elf()).hexdigest()
        )
        self.assertEqual(run.call_args.args[0][-1], "-version")
        self.assertNotIn("PYTHONPATH", run.call_args.kwargs["env"])
        self.assertEqual(run.call_args.kwargs["env"]["PATH"], "/usr/bin:/bin")

    def test_failed_version_leaves_no_install_or_staging(self):
        """Wrapper version text, bad exit status and launch failures fail atomically."""
        digest = self.wheel_bytes([(INSTALL.ENGINE, elf())])
        destination = self.root / "never-created"
        for result in (
            subprocess.CompletedProcess([], 0, b"wrapper 1.187.0", b"private"),
            subprocess.CompletedProcess([], 1, b"1.187.0", b"private"),
            OSError("private"),
        ):
            with (
                patch.object(INSTALL, "host_platform", return_value="linux-x86_64"),
                patch.dict(INSTALL.WHEELS, {"linux-x86_64": digest}),
                patch.object(
                    INSTALL.subprocess,
                    "run",
                    side_effect=result if isinstance(result, OSError) else None,
                    return_value=result,
                ),
            ):
                with self.assertRaises((INSTALL.InstallError, OSError)):
                    INSTALL.install(self.wheel, destination)
            self.assertFalse(destination.exists())
            self.assertFalse(list(self.root.glob(".park-semgrep-*")))

    def test_existing_destination_is_never_overwritten(self):
        """Existing files and dangling symlinks remain untouched without execution."""
        digest = self.wheel_bytes([(INSTALL.ENGINE, elf())])
        destination = self.root / "existing"
        destination.symlink_to(self.root / "missing")
        with (
            patch.object(INSTALL, "host_platform", return_value="linux-x86_64"),
            patch.dict(INSTALL.WHEELS, {"linux-x86_64": digest}),
            patch.object(INSTALL.subprocess, "run") as run,
        ):
            with self.assertRaises(INSTALL.InstallError):
                INSTALL.install(self.wheel, destination)
            run.assert_not_called()
        self.assertTrue(destination.is_symlink())
        self.assertEqual(os.readlink(destination), str(self.root / "missing"))


if __name__ == "__main__":
    unittest.main()
