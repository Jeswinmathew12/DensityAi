# Jetson setup runbook

How to rebuild the DensityAI Jetson from scratch and get a live count on the dashboard. This is the up-to-date source of truth. [occupancy-tracker-plan.md](../occupancy-tracker-plan.md) has the background and the reasoning behind the design.

Everything here has been run on the real hardware. Where this runbook and the plan disagree, trust this runbook.

## What is on the Jetson

| Item | Value |
|---|---|
| Board | Jetson Orin Nano 8GB dev kit |
| Storage | 256 GB NVMe, root filesystem on `/dev/nvme0n1p1`. It came pre-flashed, no reflash was needed. |
| JetPack | 6.2.1 (L4T R36.4.4, `nvidia-jetpack 6.2.1+b38`) |
| OS / Python | Ubuntu 22.04.5, Python 3.10 |
| DeepStream | 7.1, installed natively (not Docker) |
| Model | PeopleNet `deployable_quantized_onnx_v2.6.3` in `~/models/peoplenet` |
| pyds | 1.2.0, installed into the system Python |
| Power mode | 25W (`nvpmodel -m 1`), `jetson_clocks` not used |
| Camera | Logitech C920, MJPEG 1280x720 @ 30 fps |
| Dashboard | Node 22 from NodeSource |

DeepStream 7.1 officially targets JetPack 6.1. It works on 6.2.x only with the `copy-hw=2` fix described in [known issue 1](#1-crash-after-two-minutes).

Two Python environments are in play, and they are not interchangeable:

- `jetson/occupancy_pipeline.py` runs with the **system `python3`**, because that is where `pyds` and `gi` are installed.
- The backend runs from **`backend/.venv`**.

## Step 1: Check versions and storage

```bash
cat /etc/nv_tegra_release        # expect R36, REVISION: 4.4
dpkg -l | grep nvidia-jetpack    # expect 6.2.1+b38
lsb_release -d                   # expect Ubuntu 22.04.5 LTS
python3 --version                # expect 3.10.x
df -h /                          # expect /dev/nvme0n1p1
```

**Success:** all five match. If JetPack is already 6.2.x and the root filesystem is on the NVMe, skip flashing.

If it isn't, flash JetPack 6.2.1 to the NVMe by following NVIDIA's *Jetson Orin Nano Developer Kit Getting Started Guide*. Phase 1 of the plan has the hardware list. Then come back here.

Never accept an Ubuntu release upgrade ([known issue 6](#6-do-not-upgrade-ubuntu)).

## Step 2: Network and clock

The Jetson has no real-time-clock battery, so the clock resets to 1970 after every power loss ([known issue 4](#4-clock-resets-to-1970)). A wrong clock makes `apt`, `git` and `pip` fail with "not valid yet" errors. Fix the network first, then the clock.

**On `ncsu-guest`** ([known issue 5](#5-ncsu-guest-network)): open a browser on the Jetson and accept the terms page. Ping is blocked there, so test with:

```bash
curl -sI https://www.google.com | head -1     # expect HTTP/2 200 (or a 3xx)
```

**Set the clock once** from an HTTPS header, then install `htpdate` so it stays synced:

```bash
sudo date -s "$(curl -sI https://www.google.com | grep -i '^date:' | cut -d' ' -f2- | tr -d '\r')"
sudo apt install -y htpdate
date
```

With no network at all, for example in a demo room, set it by hand:

```bash
sudo date -s "YYYY-MM-DD HH:MM"
```

**Success:** `date` shows the right time and `sudo apt update` runs without "not valid yet" errors.

For laptop access to the Jetson, use a phone hotspot. Find the Jetson's address with `hostname -I`.

## Step 3: Power mode

```bash
grep "POWER_MODEL ID" /etc/nvpmodel.conf     # list the modes
sudo nvpmodel -m 1                           # 25W
sudo nvpmodel -q                             # confirm
```

On this board the modes are:

| ID | Mode |
|---|---|
| 0 | 15W |
| 1 | 25W (what we run) |
| 2 | MAXN_SUPER |
| 3 | 7W |

Do **not** run `jetson_clocks`. The plan's old `nvpmodel -m 0  # MAXN` is wrong for this board, because mode 0 is 15W.

A "System throttled due to over-current" popup still appears now and then at 25W. It is harmless board protection. If it distracts on demo day, switch to 15W with `sudo nvpmodel -m 0`. MAXN_SUPER and `jetson_clocks` make the popup much more frequent.

## Step 4: Install DeepStream 7.1

Install the prerequisites first. This is the list from Phase 2 of the plan, plus `v4l-utils`:

```bash
sudo apt install -y libssl3 libssl-dev libgstreamer1.0-0 gstreamer1.0-tools \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav libgstreamer-plugins-base1.0-dev libgstrtspserver-1.0-dev \
  libjansson4 libyaml-cpp-dev libjsoncpp-dev protobuf-compiler gcc make git python3 \
  v4l-utils
```

Then pick one install route:

```bash
apt-cache policy deepstream-7.1
```

- **A 7.1 candidate is listed:**
  ```bash
  sudo apt install -y deepstream-7.1
  ```
- **No candidate:** download the Jetson `.deb` from [developer.nvidia.com/deepstream-getting-started](https://developer.nvidia.com/deepstream-getting-started), then:
  ```bash
  sudo apt install -y ./deepstream-7.1_*_arm64.deb
  ```

Verify:

```bash
deepstream-app --version-all
```

**Success:** it reports DeepStream 7.1 along with the CUDA and TensorRT versions.

Do **not** use the DeepStream 7.1 Docker container. It has a GPU driver version mismatch on JetPack 6.2.1.

## Step 5: Check the camera

```bash
v4l2-ctl --list-devices
v4l2-ctl -d /dev/video0 --list-formats-ext
```

**Success:** the C920 appears as `/dev/video0` and lists `MJPG` at 1280x720 and 30 fps. The pipeline asks for MJPEG explicitly. Raw YUYV caps at about 10 fps at 720p.

If you get "permission denied", add yourself to the `video` group with `sudo usermod -aG video $USER`, then log out and back in.

## Step 6: PeopleNet

```bash
bash jetson/setup_peoplenet.sh
```

The script downloads PeopleNet `deployable_quantized_onnx_v2.6.3` into `~/models/peoplenet` and writes `config_infer_peoplenet.txt` with absolute paths for your `$HOME`. It is safe to re-run:

- It skips the download if the model files are already there.
- It never touches `.engine` files.
- It won't overwrite an existing config unless you pass `--force`.

The manual equivalent of the download:

```bash
mkdir -p ~/models/peoplenet && cd ~/models/peoplenet
wget --content-disposition 'https://api.ngc.nvidia.com/v2/models/nvidia/tao/peoplenet/versions/deployable_quantized_onnx_v2.6.3/zip' -O peoplenet.zip && unzip peoplenet.zip
```

After the unzip and the first pipeline run, the directory holds:

| File | What it is |
|---|---|
| `resnet34_peoplenet.onnx` | The model. It is **not** `resnet34_peoplenet_int8.onnx`. |
| `resnet34_peoplenet_int8.txt` | INT8 calibration cache |
| `labels.txt` | Class labels |
| `nvinfer_config.txt` | NVIDIA's sample config from the zip. Unused. |
| `config_infer_peoplenet.txt` | Our config, written by the script |
| `resnet34_peoplenet.onnx_b1_gpu0_int8.engine` | TensorRT engine, built on the first run |
| `peoplenet.zip` | The download |

The engine is specific to this device and TensorRT version. Never commit it, and never copy it to another Jetson.

Two rules keep the config working:

- `model-engine-file` must equal `<onnx-file path>_b1_gpu0_int8.engine`, or the engine is rebuilt on every run ([known issue 3](#3-tensorrt-engine-rebuilds-every-run)).
- Comments must start with `#` ([known issue 2](#2-config-files-only-accept-hash-comments)).

**Success:** `~/models/peoplenet/config_infer_peoplenet.txt` exists and its paths point at real files.

## Step 7: Install pyds

pyds are the Python bindings for DeepStream metadata. Use version 1.2.0, the release for DeepStream 7.1.

```bash
sudo apt install -y python3-gi python3-dev python3-gst-1.0 python3-numpy
cd /opt/nvidia/deepstream/deepstream/sources
sudo git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps.git
cd deepstream_python_apps && sudo git checkout v1.2.0

cd ~
wget https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases/download/v1.2.0/pyds-1.2.0-cp310-cp310-linux_aarch64.whl
pip3 install ./pyds-1.2.0-cp310-cp310-linux_aarch64.whl
```

If that wheel URL returns 404, download `pyds-1.2.0-cp310-cp310-linux_aarch64.whl` from the v1.2.0 release page of `NVIDIA-AI-IOT/deepstream_python_apps`.

Verify, using the system `python3`:

```bash
python3 -c "import gi, pyds; print('pyds ok')"
python3 -c "import numpy; print(numpy.__version__)"     # must be 1.x
```

numpy 2.x is not supported. If you see 2.x, run `pip3 install "numpy<2"`.

**Success:** both commands run without errors and numpy is 1.x.

## Step 8: Backend

```bash
sudo apt install -y python3.10-venv python3-pip
git clone https://github.com/Jeswinmathew12/DensityAi.git && cd DensityAi
git checkout dashboard
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
```

Without the `python3.10-venv` package, creating the venv fails.

Run the backend:

```bash
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --port 8000
```

Add `--host 0.0.0.0` only if another device needs to reach it. The pipeline on the Jetson posts to `localhost`, so the default is enough for that. If you set `INGEST_TOKEN` on the backend, set the same value for the pipeline.

Check it from a second terminal:

```bash
curl http://localhost:8000/api/health
```

**Success:** JSON listing `cam-1`, shown as stale until the pipeline starts. The camera must be listed in `backend/zones.json`. Before collecting real data, read [known issue 8](#8-stale-simulator-data-in-the-database).

## Step 9: Run the pipeline

With the backend running, in another terminal and from the repo root:

```bash
export DENSITY_API_URL=http://localhost:8000     # the default
export INGEST_TOKEN=...                          # only if the backend has one
python3 jetson/occupancy_pipeline.py             # add --no-display over SSH
```

The first run builds the TensorRT engine, which takes 3 to 10 minutes and looks like a hang. It is cached afterwards.

**Success:**
- The terminal prints the ROI count and FPS about once a second.
- Walking in front of the camera changes the count.
- `curl http://localhost:8000/api/zones` shows a matching `occupancy`.
- The pipeline is still running after 5 minutes. If it dies at about 2 minutes, see [known issue 1](#1-crash-after-two-minutes).

Don't run `backend/simulator.py` at the same time ([known issue 7](#7-simulator-and-pipeline-both-post-as-cam-1)).

Ctrl+C stops the pipeline cleanly.

## Step 10: Dashboard

### On a laptop

```bash
REACT_APP_API_URL=http://<jetson-ip>:8000 npm run start:live
```

This needs the backend started with `--host 0.0.0.0`, and a network where the laptop can reach the Jetson. Use a phone hotspot ([known issue 5](#5-ncsu-guest-network)). The backend only allows a dashboard served from `http://localhost:3000`, so run the dev server on the laptop as shown.

### On the Jetson

Ubuntu's own `nodejs` is too old for `react-scripts` 5, so use Node 22 from NodeSource:

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node --version      # v22.x
cd DensityAi && npm install
```

For development:

```bash
npm run start:live
```

For demo day, a static build uses less memory than the dev server:

```bash
REACT_APP_DATA_SOURCE=live npm run build
python3 -m http.server 3000 --directory build
```

Open `http://localhost:3000` in a browser **on the Jetson**. The backend's CORS rules already allow `localhost:3000`. Opening the Jetson's dashboard from another device would need a different API URL baked into the build and a CORS change in the backend, which this runbook does not cover.

**Success:** the dashboard shows Zone A with a live count that follows the camera.

## Step 11: One command and start at boot

`npm run serve` runs the backend (port 8000, all devices) and the pipeline together, and restarts the pipeline when it stops. `sudo jetson/install-service.sh` makes that start at boot as the `densityai` systemd service. See "How to run on the Jetson" in the README for the details.

**Success:** after a reboot, `journalctl -u densityai -f` shows `[start] Dashboard: http://...` and pipeline output, and the dashboard opens from a laptop on the same network.

## Debugging with gst-launch

If the Python app misbehaves, run the same chain without any Python. It tells you whether the problem is the camera, the model or the app.

```bash
gst-launch-1.0 v4l2src device=/dev/video0 ! \
  image/jpeg,width=1280,height=720,framerate=30/1 ! jpegdec ! videoconvert ! \
  nvvideoconvert copy-hw=2 ! 'video/x-raw(memory:NVMM),format=NV12' ! \
  m.sink_0 nvstreammux name=m batch-size=1 width=1280 height=720 live-source=1 ! \
  nvinfer config-file-path=$HOME/models/peoplenet/config_infer_peoplenet.txt ! \
  nvvideoconvert copy-hw=2 ! nvdsosd ! nv3dsink sync=false
```

**Success:** a window shows boxes around people, live. Both `nvvideoconvert` elements need `copy-hw=2`, or it dies after about two minutes.

## Known issues

### 1. Crash after two minutes

- **Symptom:** the pipeline runs for about two minutes, then dies with `nvbufsurftransform_copy.cpp:341: => Failed in mem copy`, followed by a cascade of `cudaErrorIllegalAddress (700)` errors.
- **Cause:** a known NVIDIA issue with DeepStream 7.1 on JetPack 6.2.x. See [DeepStream SDK FAQ, item 51](https://forums.developer.nvidia.com/t/deepstream-sdk-faq/80236/61).
- **Fix:** set `copy-hw=2` on **every** `nvvideoconvert`. In gst-launch that is `nvvideoconvert copy-hw=2`. In Python it is `conv.set_property("copy-hw", 2)`. This is verified stable.
- **If it ever returns:** use hardware MJPEG decode (`nvv4l2decoder mjpeg=1` in place of `jpegdec ! videoconvert`), or reflash to JetPack 6.1.

### 2. Config files only accept hash comments

- **Symptom:** an nvinfer or nvdsanalytics config fails to parse, or a value is silently wrong.
- **Cause:** DeepStream configs are GLib key files. Comment lines must start with `#`. Lines starting with `;` and inline `; ...` comments break parsing.
- **Fix:** use only `#` comments, on their own lines. The original config in the plan used `;`, and has been fixed.

### 3. TensorRT engine rebuilds every run

- **Symptom:** every start spends 3 to 10 minutes building an engine.
- **Cause:** `model-engine-file` doesn't match the name DeepStream saves the engine under, which is `<onnx-file path>_b1_gpu0_int8.engine`.
- **Fix:** make them match. In our config that is `resnet34_peoplenet.onnx_b1_gpu0_int8.engine`.
- **If the INT8 build ever fails:** set `network-mode=2` and use `_fp16.engine` as the suffix.

### 4. Clock resets to 1970

- **Symptom:** `apt`, `git` or `pip` fail with "not valid yet" certificate errors after a power loss.
- **Cause:** the Jetson has no RTC battery, and `ncsu-guest` blocks NTP.
- **Fix:** set the clock as shown in [Step 2](#step-2-network-and-clock), then install `htpdate`. With no network, set it by hand.

### 5. ncsu-guest network

- **Symptom:** no traffic at all, ping fails, or a laptop can't reach the Jetson.
- **Cause:**
  - You must accept the terms page in a browser before anything works.
  - Ping is blocked, so it is a bad test.
  - Laptop-to-Jetson traffic is likely blocked.
- **Fix:**
  - Accept the terms page, and test with `curl -sI https://www.google.com | head -1`.
  - Use a phone hotspot for laptop access.
  - Long term, register the Jetson's MAC address on the `ncsu` (Nomad) network. Get it with `cat /sys/class/net/wlP1p1s0/address`.

### 6. Do not upgrade Ubuntu

- **Symptom:** Ubuntu offers a release upgrade from 22.04 to 24.04.
- **Cause:** JetPack 6.x is built for 22.04.
- **Fix:** decline it. Accepting breaks JetPack and requires a reflash.

### 7. Simulator and pipeline both post as cam-1

- **Symptom:** the live count jumps between two unrelated values.
- **Cause:** `backend/simulator.py` and the real pipeline both post as `cam-1`.
- **Fix:** stop the simulator while the real pipeline runs.

### 8. Stale simulator data in the database

- **Symptom:** history for Demo 2 includes fake rows.
- **Cause:** `backend/density.db` holds simulator rows from testing.
- **Fix:** stop the backend and delete `backend/density.db` before collecting real data. It is recreated on the next start.

## What is not in git

These exist only on the Jetson, and this runbook rebuilds them:

- The PeopleNet model files and the TensorRT engine in `~/models/peoplenet` (Step 6)
- The DeepStream install and `pyds` (Steps 4 and 7)
- `backend/.venv` and `backend/density.db` (Step 8)
- The power mode and the clock fix (Steps 2 and 3)
