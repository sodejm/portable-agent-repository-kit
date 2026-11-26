#!/usr/bin/env bash
# Provision the latest stable scanners for the unprivileged Linux x86_64 job.
set -euo pipefail
work=$(mktemp -d "${RUNNER_TEMP:?}/assurance.XXXXXXXX")
mkdir "$work/bin"
cd "$work"
for name in gitleaks trivy; do
    release=$(python3 -I -S "$GITHUB_WORKSPACE/tools/push_gate/scanner_release.py" "$name" artifact)
    url=$(jq -er '.url' <<< "$release")
    digest=$(jq -er '.sha256' <<< "$release")
    version=$(jq -er '.version' <<< "$release")
    curl --disable --fail --silent --show-error --location --retry 3 --proto '=https' --proto-redir '=https' \
        --max-time 180 --output package.tar.gz "$url"
    echo "$digest  package.tar.gz" | sha256sum --check --status
    tar -xzf package.tar.gz -C "$work/bin" "$name"
    printf '%s %s SHA-256 %s\n' "$name" "$version" "$digest"
done
python3 -I -S "$GITHUB_WORKSPACE/tools/push_gate/install_native_semgrep.py" latest "$work/native"
printf '%s\n' "$work/bin" "$work/native/semgrep/bin" >> "${GITHUB_PATH:?}"
