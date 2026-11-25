#!/usr/bin/env python3
"""Install only the pinned wheel's native engine and linked bundled libraries.

This offline, standard-library installer never installs/imports wheel Python code
or resolves dependencies. The operator supplies an official wheel and a new
destination in a trusted parent directory. A digest mismatch fails before ZIP
parsing; extraction is bounded and manual, never ZipFile.extract/all.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import stat
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

VERSION = "1.187.0"
WHEELS = {
    "macos-arm64": "a44a8f486719e69fe38c451c70b4808bed5532bbcb4c25a8dd04a74617dfcca0",
    "linux-aarch64": "79f0a3dc63607fada4ae2225599ab5eef8005124a8484814184df72805afcfc0",
    "linux-x86_64": "ad160ed527bd153b96616814366a6d17f451d37babf75df6705327aede0cc8bd",
}
ENGINE = "semgrep/bin/semgrep-core"
MAX_WHEEL = 256 * 1024 * 1024
MAX_PAYLOAD = 512 * 1024 * 1024
SYSTEM_ELF = {
    "libc.so.6",
    "libm.so.6",
    "libdl.so.2",
    "libpthread.so.0",
    "librt.so.1",
    "libstdc++.so.6",
    "libgcc_s.so.1",
    "ld-linux-aarch64.so.1",
    "ld-linux-x86-64.so.2",
}


class InstallError(RuntimeError):
    """Invalid platform, distribution, payload or destination; no fallback allowed."""


def host_platform():
    """Select supported native hosts; Linux needs glibc >=2.34, never musl."""
    machine = platform.machine().lower()
    if sys.platform == "darwin" and machine == "arm64":
        return "macos-arm64"
    if sys.platform == "linux" and machine in {"aarch64", "x86_64"}:
        libc, version = platform.libc_ver()
        try:
            compatible = tuple(int(part) for part in version.split(".")[:2]) >= (2, 34)
        except ValueError:
            compatible = False
        if libc == "glibc" and compatible:
            return "linux-" + machine
    raise InstallError(
        "Unsupported host: need native macOS ARM64 or Linux glibc >=2.34 ARM64/x86_64"
    )


def cstring(data, offset):
    """Read a bounded native string table entry, rejecting truncation."""
    if not 0 <= offset < len(data):
        raise InstallError("Invalid native string offset")
    end = data.find(b"\0", offset)
    if end < 0:
        raise InstallError("Unterminated native string")
    return data[offset:end].decode("utf-8", errors="strict")


def dependencies(data, target):
    """Read linked library names without executing payloads or using host tools.

    Only little-endian ELF64 and thin Mach-O ARM64 are supported. ELF dynamic
    strings are addressed through PT_LOAD mappings; Mach-O names come from load
    commands, excluding LC_ID_DYLIB (the library's own identity).
    """
    if target == "macos-arm64":
        magic, cpu = struct.unpack_from("<II", data)
        if magic != 0xFEEDFACF or cpu != 0x0100000C:
            raise InstallError("Expected native Mach-O ARM64 payload")
        count, size = struct.unpack_from("<II", data, 16)
        offset, end = 32, 32 + size
        if end > len(data) or count > 4096:
            raise InstallError("Invalid Mach-O load commands")
        names = []
        for _ in range(count):
            command, length = struct.unpack_from("<II", data, offset)
            if length < 8 or offset + length > end:
                raise InstallError("Invalid Mach-O command size")
            if command in {0xC, 0x80000018, 0x8000001F, 0x20, 0x80000023}:
                position = struct.unpack_from("<I", data, offset + 8)[0]
                names.append(cstring(data[offset : offset + length], position))
            offset += length
        if offset != end:
            raise InstallError("Invalid Mach-O command boundary")
        return names
    expected_cpu = 183 if target == "linux-aarch64" else 62
    if (
        data[:6] != b"\x7fELF\x02\x01"
        or struct.unpack_from("<H", data, 18)[0] != expected_cpu
    ):
        raise InstallError("Expected native ELF64 payload")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    entry_size, count = struct.unpack_from("<HH", data, 54)
    if entry_size != 56 or count > 4096 or phoff + count * entry_size > len(data):
        raise InstallError("Invalid ELF program headers")
    segments, dynamic = [], None
    for index in range(count):
        kind, _, offset, address, _, size, _, _ = struct.unpack_from(
            "<IIQQQQQQ", data, phoff + index * entry_size
        )
        if offset + size > len(data):
            raise InstallError("Invalid ELF segment")
        if kind == 1:
            segments.append((address, offset, size))
        if kind == 2:
            dynamic = (offset, size)
    if dynamic is None:
        return []
    offset, size = dynamic
    needed, table, table_size = [], None, None
    for position in range(offset, offset + size, 16):
        tag, value = struct.unpack_from("<QQ", data, position)
        if tag == 0:
            break
        if tag == 1:
            needed.append(value)
        if tag == 5:
            table = value
        if tag == 10:
            table_size = value
    if not needed:
        return []
    if table is None or table_size is None:
        raise InstallError("Missing ELF dynamic string table")
    names = []
    for position in needed:
        if position >= table_size:
            raise InstallError("Invalid ELF string offset")
        for address, offset, size in segments:
            displacement = table + position - address
            if 0 <= displacement < size:
                start = offset + displacement
                end = start + min(table_size - position, size - displacement)
                names.append(cstring(data[start:end], 0))
                break
        else:
            raise InstallError("Unmapped ELF dependency name")
    return names


def native_payload(wheel, digest, target):
    """Verify bytes and return only the engine and its bundled dependency closure.

    All ZIP names/types are preflighted, including discarded members. Linked
    libraries retain wheel-relative paths for loader-relative references. Missing
    non-system dependencies and ambiguous library basenames fail closed.
    """
    with wheel.open("rb") as source:
        data = source.read(MAX_WHEEL + 1)
    if len(data) > MAX_WHEEL or hashlib.sha256(data).hexdigest() != digest:
        raise InstallError("Wheel SHA256 mismatch or size limit exceeded")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = {}
        infos = archive.infolist()
        if len(infos) > 8192:
            raise InstallError("Wheel member limit exceeded")
        for info in infos:
            name = info.filename
            parts = PurePosixPath(name).parts
            mode = info.external_attr >> 16
            if (
                not parts
                or name.startswith("/")
                or "\\" in name
                or any(part in {"", ".", ".."} for part in name.rstrip("/").split("/"))
                or any(ord(char) < 32 for char in name)
                or ":" in name
                or info.orig_filename != name
                or name in entries
                or stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}
                or info.flag_bits & 1
            ):
                raise InstallError("Unsafe or duplicate wheel member")
            installed_name = name.removeprefix(f"semgrep-{VERSION}.data/purelib/")
            if installed_name in entries:
                raise InstallError("Duplicate wheel installation path")
            entries[installed_name] = info
        if ENGINE not in entries:
            raise InstallError("Wheel has no native engine")
        libraries = {}
        for name, info in entries.items():
            path = PurePosixPath(name)
            if not info.is_dir() and (
                name.startswith("semgrep/bin/") or name.startswith("semgrep.libs/")
            ):
                if ".so" in path.name or path.name.endswith(".dylib"):
                    libraries.setdefault(path.name, []).append(name)
        payload, pending, total = {}, [ENGINE], 0
        while pending:
            name = pending.pop()
            if name in payload:
                continue
            info = entries[name]
            total += info.file_size
            if info.is_dir() or info.file_size <= 0 or total > MAX_PAYLOAD:
                raise InstallError("Invalid native payload size")
            body = archive.read(info)
            payload[name] = body
            for dependency in dependencies(body, target):
                matches = libraries.get(PurePosixPath(dependency).name, [])
                if len(matches) == 1:
                    pending.append(matches[0])
                elif matches or not (
                    (
                        target == "macos-arm64"
                        and dependency.startswith(("/usr/lib/", "/System/Library/"))
                    )
                    or (target.startswith("linux-") and dependency in SYSTEM_ELF)
                ):
                    raise InstallError("Missing or ambiguous bundled native library")
        return payload


def install(wheel, destination):
    """Publish a new native-only directory after verifying the raw engine version.

    Refuse existing destinations. Staging stays in the destination's trusted
    parent and is removed on failure. The installer never changes PATH or hooks.
    """
    target = host_platform()
    payload = native_payload(wheel, WHEELS[target], target)
    if destination.exists() or destination.is_symlink():
        raise InstallError("Destination already exists; choose a new directory")
    with tempfile.TemporaryDirectory(
        prefix=".park-semgrep-", dir=destination.parent
    ) as temporary:
        staging = Path(temporary) / "native"
        staging.mkdir()
        for name, body in sorted(payload.items()):
            output = staging / name
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(body)
            output.chmod(0o755 if name == ENGINE else 0o644)
        engine = staging / ENGINE
        os.link(engine, engine.with_name("osemgrep"))
        # Do not let loader or Python environment overrides affect verification.
        env = {"PATH": "/usr/bin:/bin", "HOME": temporary, "LC_ALL": "C"}
        result = subprocess.run(
            [str(engine), "-version"],
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if (
            result.returncode
            or result.stdout.strip()
            != f"semgrep-core version: {VERSION} (a5341ae595)".encode()
        ):
            raise InstallError("Native engine version verification failed")
        manifest = {
            "version": VERSION,
            "platform": target,
            "wheel_sha256": WHEELS[target],
            "files": {
                name: hashlib.sha256(body).hexdigest()
                for name, body in sorted(payload.items())
            },
        }
        manifest["files"]["semgrep/bin/osemgrep"] = manifest["files"][ENGINE]
        (staging / "native-install.json").write_text(
            json.dumps(manifest, sort_keys=True, indent=2) + "\n"
        )
        staging.rename(destination)


def main():
    """Accept local inputs only and emit sanitized success/failure diagnostics."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        install(args.wheel, args.destination.absolute())
    except (
        InstallError,
        OSError,
        ValueError,
        struct.error,
        zipfile.BadZipFile,
        subprocess.SubprocessError,
        RuntimeError,
    ):
        print(
            "Native Semgrep installation failed; verify wheel, host and new destination",
            file=sys.stderr,
        )
        return 1
    print(
        "Installed native Semgrep "
        + VERSION
        + "; no Python dependency packages installed"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
