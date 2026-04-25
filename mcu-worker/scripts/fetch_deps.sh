#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
THIRD_PARTY_DIR="$ROOT_DIR/third_party"
NANOPB_DIR="$THIRD_PARTY_DIR/nanopb"
WASM3_DIR="$THIRD_PARTY_DIR/wasm3"
PATCH_DIR="$ROOT_DIR/scripts/patches"

NANOPB_REPO="https://github.com/nanopb/nanopb.git"
WASM3_REPO="https://github.com/wasm3/wasm3.git"

mkdir -p "$THIRD_PARTY_DIR"

if [ ! -d "$NANOPB_DIR" ]; then
  git clone --depth 1 "$NANOPB_REPO" "$NANOPB_DIR"
fi

if [ ! -d "$WASM3_DIR" ]; then
  git clone --depth 1 "$WASM3_REPO" "$WASM3_DIR"
fi

apply_repo_patch() {
  local repo_dir="$1"
  local patch_file="$2"

  if git -C "$repo_dir" apply --reverse --check "$patch_file" >/dev/null 2>&1; then
    return 0
  fi

  git -C "$repo_dir" apply "$patch_file"
}

apply_repo_patch "$NANOPB_DIR" "$PATCH_DIR/nanopb-protobuf-6.33.6.patch"
apply_repo_patch "$WASM3_DIR" "$PATCH_DIR/wasm3-esp32-build.patch"
