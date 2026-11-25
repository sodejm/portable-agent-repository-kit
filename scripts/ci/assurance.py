"""Run cumulative project assurance on a disposable copy of the committed tree."""

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/push_gate"))
import gate

LEVELS = ("low", "medium", "high", "critical")


def tier(root):
    """Read the project's selected assurance level, including critical review policy."""
    profile = root / ".park/profile.json"
    if not profile.exists() and (root / ".portable-agent-template").is_file():
        return "low"
    data = json.loads(profile.read_bytes())
    if not isinstance(data, dict) or type(data.get("version")) is not int or data["version"] != 1 or data.get("assurance") not in LEVELS:
        raise ValueError("invalid .park/profile.json version or assurance")
    if data["assurance"] == "critical":
        policy = json.loads((root / ".github/review-policy.json").read_bytes())
        if policy.get("require_independent_review") is not True:
            raise ValueError("critical assurance requires independent review in .github/review-policy.json")
    return data["assurance"]


def check_recovery(root, today):
    """Require a successful, identified recovery exercise within the past 90 days."""
    record = json.loads((root / ".park/recovery.json").read_bytes())
    for field in ("date", "environment", "procedure", "evidence", "reviewer"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"missing recovery {field}")
    age = today - dt.date.fromisoformat(record["date"])
    if record.get("result") != "passed" or not dt.timedelta() <= age <= dt.timedelta(days=90):
        raise ValueError("critical release requires a passed recovery exercise within 90 days")


def scan(root, output):
    """Check history and committed files, publishing the SBOM only after success."""
    sha = gate.git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    files = [name for _, _, name in gate.tree(root, sha)]
    env = gate.clean_environment()
    with tempfile.TemporaryDirectory(prefix="park-assurance-") as work:
        private = Path(work)
        snapshot = private / "snapshot"
        git = ["git", "-c", "core.hooksPath=" + os.devnull]
        gate.run([*git, "clone", "--no-checkout", "--no-hardlinks", "--template=", str(root), str(snapshot)], private, env=env)
        gate.run([*git, "checkout", "--detach", sha], snapshot, env=env)
        level = tier(snapshot)
        config = private / "gitleaks.toml"
        config.write_text("[extend]\nuseDefault = true\n", encoding="utf-8")
        ignore = private / "empty"
        ignore.touch()
        policy = json.loads((snapshot / "tools/push_gate/policy.json").read_bytes())
        selected = gate.required_version("gitleaks", policy, snapshot, env)
        if gate.run(["gitleaks", "version"], snapshot, env=env).decode().strip() != selected:
            raise ValueError(f"Required Gitleaks version: {selected}")
        for mode, options in (("git", ["--log-opts=HEAD"]), ("dir", [])):
            gate.run(["gitleaks", mode, "--redact=100", "--no-banner", "--ignore-gitleaks-allow",
                      "--gitleaks-ignore-path", str(ignore), "--config", str(config), *options, "."], snapshot, env=env)
        gate.scanners(snapshot, files, policy, env, private)
        if level != "low":
            report = private / "sbom.json"
            gate.run(["trivy", "fs", "--config", "", "--skip-dirs", ".git", "--format", "cyclonedx",
                      "--output", str(report), "."], snapshot, env=env)
            if json.loads(report.read_bytes()).get("bomFormat") != "CycloneDX":
                raise ValueError("invalid CycloneDX output")
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=output, delete=False) as staged:
                with report.open("rb") as source:
                    shutil.copyfileobj(source, staged)
            os.replace(staged.name, output / "sbom.cdx.json")
    print(f"Passed {level} scans at {sha}")


def main():
    """Dispatch scan, tier discovery or critical-release recovery validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tier", "scan", "recovery"))
    parser.add_argument("--output-dir", type=Path, default=ROOT / "tmp/assurance")
    args = parser.parse_args()
    if args.command == "tier":
        print(tier(ROOT))
    elif args.command == "scan":
        scan(ROOT, args.output_dir)
    else:
        check_recovery(ROOT, dt.datetime.now(dt.timezone.utc).date())


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, AttributeError, gate.GateError) as error:
        sys.exit(f"assurance failed: {error}")
