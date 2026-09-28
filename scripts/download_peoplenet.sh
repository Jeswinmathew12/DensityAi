#!/usr/bin/env bash
# Download PeopleNet deployable_quantized_onnx_v2.6.3 from NGC into models/peoplenet/.
# PeopleNet is a public NGC model, so no API key is needed.
#
# Usage: ./scripts/download_peoplenet.sh [target-dir]
set -euo pipefail

VERSION="deployable_quantized_onnx_v2.6.3"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-$REPO_ROOT/models/peoplenet}"
ZIP_URL="https://api.ngc.nvidia.com/v2/models/org/nvidia/team/tao/peoplenet/${VERSION}/zip"

# File names config_infer_peoplenet.txt expects
ONNX="resnet34_peoplenet_int8.onnx"
CALIB="resnet34_peoplenet_int8.txt"

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

if [[ -f "$ONNX" && -f "$CALIB" ]]; then
  echo "PeopleNet already present in $TARGET_DIR"
  exit 0
fi

if command -v ngc >/dev/null 2>&1; then
  echo "Downloading with NGC CLI..."
  ngc registry model download-version "nvidia/tao/peoplenet:${VERSION}" --dest .
  # The CLI unpacks into peoplenet_v<version>/; flatten it
  shopt -s nullglob
  for d in peoplenet_v*/; do
    mv -n "$d"* . && rmdir "$d"
  done
  shopt -u nullglob
else
  command -v unzip >/dev/null 2>&1 || { echo "unzip is required: sudo apt install unzip" >&2; exit 1; }
  echo "Downloading $ZIP_URL ..."
  curl -fL --retry 3 -o peoplenet.zip "$ZIP_URL"
  unzip -o peoplenet.zip
  rm -f peoplenet.zip
fi

# If NGC ships the files under different names, link them to what the config expects
link_if_missing() {
  local want="$1" pattern="$2"
  [[ -f "$want" ]] && return 0
  mapfile -t found < <(ls $pattern 2>/dev/null || true)
  if [[ ${#found[@]} -eq 1 ]]; then
    ln -sf "${found[0]}" "$want"
    echo "Linked ${found[0]} -> $want"
  else
    echo "Could not find $want (candidates: ${found[*]:-none}). Update configs/config_infer_peoplenet.txt to match." >&2
    return 1
  fi
}
link_if_missing "$ONNX" "*.onnx"
link_if_missing "$CALIB" "*int8*.txt"

echo
echo "PeopleNet ready in $TARGET_DIR:"
ls -l "$TARGET_DIR"
