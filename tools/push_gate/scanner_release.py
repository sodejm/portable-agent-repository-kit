"""Resolve a stable scanner release and verify its official artifact identity."""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

GITHUB = {
    "gitleaks": ("gitleaks/gitleaks", "gitleaks_{}_linux_x64.tar.gz"),
    "trivy": ("aquasecurity/trivy", "trivy_{}_Linux-64bit.tar.gz"),
}
WHEEL_PLATFORMS = {
    "macos-arm64": "macosx_11_0_arm64",
    "linux-aarch64": "manylinux_2_34_aarch64",
    "linux-x86_64": "manylinux_2_34_x86_64",
}
CURL = [
    "curl",
    "--disable",
    "--fail",
    "--silent",
    "--show-error",
    "--location",
    "--proto",
    "=https",
    "--proto-redir",
    "=https",
    "--retry",
    "3",
    "--max-time",
    "120",
]


def release_version(tool, metadata):
    """Reject drafts, prereleases and unexpected version text from upstream."""
    if tool == "semgrep":
        version = metadata["info"]["version"]
    else:
        if metadata["draft"] is not False or metadata["prerelease"] is not False:
            raise ValueError("Expected a published stable release")
        version = metadata["tag_name"].removeprefix("v")
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version):
        raise ValueError("Expected a stable three-part scanner version")
    return version


def artifact(tool, metadata, target):
    """Select one exact platform artifact with an upstream SHA-256 digest."""
    version = release_version(tool, metadata)
    if tool == "semgrep":
        matches = [
            item
            for item in metadata["urls"]
            if item["packagetype"] == "bdist_wheel"
            and item["yanked"] is False
            and item["filename"].startswith(f"semgrep-{version}-")
            and item["filename"].endswith(".whl")
            and WHEEL_PLATFORMS[target]
            in item["filename"][:-4].rsplit("-", 1)[-1].split(".")
        ]
        if len(matches) != 1:
            raise ValueError("Expected one supported Semgrep wheel")
        item = matches[0]
        url, digest = item["url"], item["digests"]["sha256"]
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.netloc != "files.pythonhosted.org"
            or Path(parts.path).name != item["filename"]
        ):
            raise ValueError("Unexpected wheel URL")
    else:
        if target != "linux-x86_64":
            raise ValueError("Only Linux x86_64 archive provisioning is supported")
        repo, pattern = GITHUB[tool]
        name = pattern.format(version)
        matches = [item for item in metadata["assets"] if item["name"] == name]
        if len(matches) != 1:
            raise ValueError("Expected one supported Linux archive")
        item = matches[0]
        url = f"https://github.com/{repo}/releases/download/v{version}/{name}"
        if item["browser_download_url"] != url:
            raise ValueError("Unexpected archive URL")
        prefix, _, digest = (item["digest"] or "").partition(":")
        if prefix != "sha256":
            raise ValueError("Missing upstream SHA-256 digest")
    if not re.fullmatch("[a-f0-9]{64}", digest):
        raise ValueError("Invalid upstream SHA-256 digest")
    return {"version": version, "url": url, "sha256": digest}


def metadata(tool):
    """Read the official stable release index over HTTPS."""
    url = (
        "https://pypi.org/pypi/semgrep/json"
        if tool == "semgrep"
        else f"https://api.github.com/repos/{GITHUB[tool][0]}/releases/latest"
    )
    return json.loads(
        subprocess.check_output([*CURL, "--max-filesize", "16777216", url])
    )


def main():
    """Print the concrete version or verified artifact metadata for provisioning."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=["semgrep", *GITHUB])
    parser.add_argument("operation", choices=["version", "artifact"])
    parser.add_argument("--platform", choices=WHEEL_PLATFORMS, default="linux-x86_64")
    args = parser.parse_args()
    data = metadata(args.tool)
    if args.operation == "version":
        print(release_version(args.tool, data))
    else:
        print(json.dumps(artifact(args.tool, data, args.platform)))


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        AttributeError,
        subprocess.SubprocessError,
    ) as error:
        sys.exit(f"Scanner release lookup failed: {error}")
