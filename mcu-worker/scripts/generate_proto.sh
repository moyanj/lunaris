#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$ROOT_DIR/.." && pwd)"
PROTO_DIR="$REPO_ROOT/proto"
MCU_PROTO_DIR="$ROOT_DIR/proto"
OUT_DIR="$ROOT_DIR/generated"
NANOPB_DIR="$ROOT_DIR/third_party/nanopb"

mkdir -p "$OUT_DIR"

protoc \
  --plugin=protoc-gen-nanopb="$NANOPB_DIR/generator/protoc-gen-nanopb" \
  --proto_path="$PROTO_DIR" \
  --proto_path="$MCU_PROTO_DIR" \
  --nanopb_out="$OUT_DIR" \
  "$PROTO_DIR/common.proto" \
  "$PROTO_DIR/worker.proto"
