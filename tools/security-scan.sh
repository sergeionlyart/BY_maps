#!/usr/bin/env bash

set -euo pipefail

repository_root="$(git rev-parse --show-toplevel)"
audit_directory="$(mktemp -d "${TMPDIR:-/tmp}/by-maps-security.XXXXXX")"
status=0

cleanup() {
  rm -rf "$audit_directory"
}

trap cleanup EXIT HUP INT TERM
cd "$repository_root"

git archive --format=tar HEAD | tar -xf - -C "$audit_directory"

if ! (
  cd "$audit_directory"
  gitleaks dir \
    --config "$repository_root/.gitleaks.toml" \
    --redact=100 \
    --max-archive-depth=2 \
    .
); then
  status=1
fi

gitleaks git \
  --config "$repository_root/.gitleaks.toml" \
  --log-opts='--all' \
  --redact=100 \
  --max-archive-depth=2 \
  . || status=1

exit "$status"
