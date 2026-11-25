#!/usr/bin/env bash
# Provision digest-verified Linux x86_64 tools for the unprivileged scan job.
set -euo pipefail
work=$(mktemp -d "${RUNNER_TEMP:?}/assurance.XXXXXXXX")
mkdir "$work/bin"
cd "$work"
fetch_binary() {
    local url=$1 digest=$2 name=$3
    curl --fail --silent --show-error --location --retry 3 "$url" --output package.tar.gz
    echo "$digest  package.tar.gz" | sha256sum --check --status
    tar -xzf package.tar.gz -C "$work/bin" "$name"
}
fetch_binary https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_linux_x64.tar.gz \
    551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb gitleaks
fetch_binary https://github.com/aquasecurity/trivy/releases/download/v0.76.2/trivy_0.76.2_Linux-64bit.tar.gz \
    bc0fc726e017b8927a62b2d3531d7a84ee01769daf5c99ed866dced54089fdbf trivy
python3 -m pip --isolated download --no-deps --only-binary=:all: --dest "$work" semgrep==1.186.0
python3 "$GITHUB_WORKSPACE/tools/push_gate/install_native_semgrep.py" "$work"/semgrep-*.whl "$work/native"
printf '%s\n' "$work/bin" "$work/native/semgrep/bin" >> "${GITHUB_PATH:?}"
