#!/usr/bin/env bash
# Live PeopleNet on the USB webcam (plan Phase 3 smoke test).
# Usage: ./scripts/run_webcam.sh [device]    default device: /dev/video0
# The first run builds the TensorRT engine (several minutes, looks frozen).
set -euo pipefail

DEVICE="${1:-/dev/video0}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$REPO_ROOT/configs/config_infer_peoplenet.txt"

[[ -e "$DEVICE" ]] || { echo "No camera at $DEVICE. Check: v4l2-ctl --list-devices" >&2; exit 1; }
[[ -f "$REPO_ROOT/models/peoplenet/resnet34_peoplenet_int8.onnx" ]] || {
  echo "PeopleNet not downloaded. Run: ./scripts/download_peoplenet.sh" >&2; exit 1; }
# Over SSH, show the window on the Jetson's own monitor
export DISPLAY="${DISPLAY:-:0}"

gst-launch-1.0 -v \
  v4l2src device="$DEVICE" ! \
  image/jpeg,width=1280,height=720,framerate=30/1 ! jpegdec ! videoconvert ! \
  nvvideoconvert ! 'video/x-raw(memory:NVMM),format=NV12' ! \
  m.sink_0 nvstreammux name=m batch-size=1 width=1280 height=720 live-source=1 ! \
  nvinfer config-file-path="$CONFIG" ! \
  nvvideoconvert ! nvdsosd ! \
  fpsdisplaysink video-sink=nv3dsink text-overlay=false sync=false
