#!/usr/bin/env bash
# Downloads PeopleNet (deployable_quantized_onnx_v2.6.3) into ~/models/peoplenet and writes
# config_infer_peoplenet.txt there, with absolute paths for the current $HOME.
#
#   bash jetson/setup_peoplenet.sh           # safe to re-run
#   bash jetson/setup_peoplenet.sh --force   # also overwrite an existing config
#
# - Skips the download if the model files are already there.
# - Never touches existing .engine files (they are device-specific TensorRT builds).
# - Won't overwrite an existing config unless --force is given.
set -euo pipefail

URL='https://api.ngc.nvidia.com/v2/models/nvidia/tao/peoplenet/versions/deployable_quantized_onnx_v2.6.3/zip'
MODEL_DIR="$HOME/models/peoplenet"
CONFIG="$MODEL_DIR/config_infer_peoplenet.txt"
FORCE=0

for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help) sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $arg (try --help)" >&2; exit 1 ;;
  esac
done

# Finds the model files in $MODEL_DIR. Sets ONNX and CALIB, or leaves them empty.
find_model_files() {
  ONNX=""
  CALIB=""
  if [ -f "$MODEL_DIR/resnet34_peoplenet.onnx" ]; then
    ONNX="$MODEL_DIR/resnet34_peoplenet.onnx"
  else
    ONNX=$(find "$MODEL_DIR" -maxdepth 1 -name '*.onnx' | sort | head -n 1)
  fi
  CALIB=$(find "$MODEL_DIR" -maxdepth 1 -name '*int8*.txt' | sort | head -n 1)
}

mkdir -p "$MODEL_DIR"
find_model_files

if [ -n "$ONNX" ] && [ -n "$CALIB" ] && [ -f "$MODEL_DIR/labels.txt" ]; then
  echo "PeopleNet files already in $MODEL_DIR, skipping download."
else
  for tool in wget unzip; do
    command -v "$tool" >/dev/null || { echo "$tool is required: sudo apt install -y $tool" >&2; exit 1; }
  done
  ZIP="$MODEL_DIR/peoplenet.zip"
  if [ -f "$ZIP" ] && unzip -tq "$ZIP" >/dev/null 2>&1; then
    echo "Using existing $ZIP"
  else
    echo "Downloading PeopleNet..."
    wget --content-disposition "$URL" -O "$ZIP.part"
    mv "$ZIP.part" "$ZIP"
  fi
  unzip -o "$ZIP" -d "$MODEL_DIR"
  find_model_files
fi

if [ -z "$ONNX" ] || [ -z "$CALIB" ] || [ ! -f "$MODEL_DIR/labels.txt" ]; then
  echo "Expected an .onnx file, an int8 calibration .txt and labels.txt in $MODEL_DIR, but not all are there." >&2
  exit 1
fi
echo "Model: $ONNX"
echo "Calibration cache: $CALIB"

if [ -f "$CONFIG" ] && [ "$FORCE" -ne 1 ]; then
  echo "$CONFIG already exists, leaving it alone (use --force to overwrite)."
  exit 0
fi

# DeepStream saves the engine as <onnx path>_b1_gpu0_int8.engine. model-engine-file must match it
# exactly, or TensorRT rebuilds the engine (3-10 min) on every run.
TMP=$(mktemp "$MODEL_DIR/.config.XXXXXX")
cat > "$TMP" <<CONF
[property]
gpu-id=0
net-scale-factor=0.0039215697906911373
onnx-file=$ONNX
int8-calib-file=$CALIB
model-engine-file=${ONNX}_b1_gpu0_int8.engine
labelfile-path=$MODEL_DIR/labels.txt
infer-dims=3;544;960
batch-size=1
# 0=FP32 1=INT8 2=FP16
network-mode=1
# classes: person, bag, face
num-detected-classes=3
interval=0
gie-unique-id=1
cluster-mode=2
output-blob-names=output_bbox/BiasAdd:0;output_cov/Sigmoid:0

[class-attrs-all]
pre-cluster-threshold=0.4
topk=20
nms-iou-threshold=0.5

# ignore bags (class 1) and faces (class 2), count people only
[class-attrs-1]
pre-cluster-threshold=1.1
[class-attrs-2]
pre-cluster-threshold=1.1
CONF
chmod 644 "$TMP"
mv "$TMP" "$CONFIG"
echo "Wrote $CONFIG"
echo "The first pipeline run builds the TensorRT engine (3-10 min). It is cached after that."
