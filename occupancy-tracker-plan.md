# Smart Occupancy Tracker — Build Plan (Jetson Orin Nano + DeepStream)

Reference repo: `NVIDIA-AI-IOT/deepstream-occupancy-analytics` — good for *logic*, outdated for *setup*. This plan replaces its install steps with current ones and adds the dashboard layer.

---

## Target architecture

```
Logitech C920 (USB, MJPEG/H264)
        │
        ▼
┌──────────────────────── Jetson Orin Nano ────────────────────────┐
│  v4l2src → nvvideoconvert → nvstreammux                          │
│      → nvinfer        (PeopleNet, person class)                  │
│      → nvtracker      (NvDCF — assigns persistent object IDs)    │
│      → nvdsanalytics  (line-crossing = entry/exit,               │
│                        ROI count      = occupancy)               │
│      → nvdsosd → display / RTSP out                              │
│                                                                  │
│  Python probe reads analytics metadata each frame                │
│      → writes to SQLite  → FastAPI REST/WebSocket server         │
└──────────────────────────────────────────────────────────────────┘
        │
        ▼
   React dashboard (browser, on-device or LAN)
```

**Key insight:** you do *not* need to write line-crossing logic. `nvdsanalytics` is a stock DeepStream plugin that does entry/exit counting and ROI occupancy for you via a config file. The old repo predates its widespread use and hand-rolls much of this in C.

---

## Phase 0 — Decisions to lock now (Day 1)

| Decision | Recommendation | Why |
|---|---|---|
| JetPack version | **6.2** (Ubuntu 22.04) | DeepStream 7.1 pairs with it; most forum answers/tutorials target this. JetPack 7.x is newer but thinly documented for third-party samples. |
| DeepStream | **7.1** | Stable, has `nvdsanalytics`, ONNX-native `nvinfer`. |
| Language | **Python** (`deepstream_python_apps` / `pyds`) | The NVIDIA repo is C. Python cuts your integration time massively and makes the dashboard hookup trivial. Performance is fine — inference still runs in TensorRT. |
| Model | **PeopleNet `deployable_quantized_onnx_v2.6.3`** | ONNX, not the legacy `.etlt`. No `tlt-converter`, no model key. |
| Data store | **SQLite** | Zero setup, file-based, plenty for a demo. Skip Kafka/Redis — the old repo uses Kafka, which is overkill here. |
| Dashboard | **FastAPI + React (or plain HTML + Chart.js)** | Runs on the Jetson, viewable from any laptop on the same network. |

---

## Phase 1 — Flash the Jetson (Days 1–3)

The Orin Nano Dev Kit no longer has an SD-card image. You flash via USB.

1. **Hardware you need:** the dev kit, 19V barrel power supply, USB-C cable (for flashing), a USB flash drive ≥16GB, an NVMe SSD (**strongly recommended** — 256GB+; DeepStream + models + engine files will fill microSD fast), monitor/keyboard/mouse, Ethernet.
2. Download the **unified JetPack 6.2 ISO** from NVIDIA's JetPack downloads page. Write it to the USB stick (`balenaEtcher` or `dd`).
3. Follow NVIDIA's **Jetson Orin Nano Developer Kit Getting Started Guide** for the USB-boot flashing procedure. Install to the NVMe, not the SD card.
4. On first boot, complete Ubuntu setup, then:
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install nvidia-jetpack -y
   ```
5. **Enable Super Mode / MAXN power profile** — big free performance win:
   ```bash
   sudo nvpmodel -m 0        # MAXN
   sudo jetson_clocks
   ```
6. Verify:
   ```bash
   sudo apt install python3-pip -y && sudo pip3 install jetson-stats
   jtop        # confirm JetPack version, CUDA, TensorRT all present
   ```

**Checkpoint:** `jtop` shows JetPack 6.2, CUDA 12.6, TensorRT 10.x.

---

## Phase 2 — Install DeepStream (Days 3–5)

Two options — pick one and have the whole team use the same:

**Option A — Native (recommended for a hardware demo)**
```bash
# Dependencies
sudo apt install -y libssl3 libssl-dev libgstreamer1.0-0 gstreamer1.0-tools \
  gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
  gstreamer1.0-libav libgstreamer-plugins-base1.0-dev libgstrtspserver-1.0-dev \
  libjansson4 libyaml-cpp-dev libjsoncpp-dev protobuf-compiler gcc make git python3

# Download the DeepStream 7.1 Jetson .deb from NVIDIA (developer.nvidia.com/deepstream-getting-started)
sudo apt install ./deepstream-7.1_*_arm64.deb
```

**Option B — Docker** (`nvcr.io/nvidia/deepstream:7.1-samples-multiarch`) — cleanest, but USB camera and display passthrough add friction.

**Verify the install with a stock sample before touching your own code:**
```bash
cd /opt/nvidia/deepstream/deepstream-7.1/samples/configs/deepstream-app
deepstream-app -c source1_usb_dec_infer_resnet_int8.txt
```
First run builds a TensorRT engine and takes several minutes. If you see bounding boxes on a window, DeepStream works.

**Checkpoint:** a sample app renders detections.

---

## Phase 3 — Camera in, PeopleNet running (Week 2)

1. **Confirm the C920:**
   ```bash
   v4l2-ctl --list-devices
   v4l2-ctl -d /dev/video0 --list-formats-ext   # note supported res/fps
   ```
   Use **MJPEG 1280x720 @30fps** — the C920's raw YUYV mode caps at ~10fps at 720p.

2. **Download PeopleNet (ONNX):**
   ```bash
   mkdir -p ~/models/peoplenet && cd ~/models/peoplenet
   # Via NGC CLI:
   ngc registry model download-version \
     "nvidia/tao/peoplenet:deployable_quantized_onnx_v2.6.3"
   # Or download the .onnx, labels.txt, and int8 calib cache directly from the
   # NGC catalog page for peoplenet.
   ```

3. **Write `config_infer_peoplenet.txt`** — this is where the old repo's config will mislead you. Modern form:
   ```ini
   [property]
   gpu-id=0
   net-scale-factor=0.0039215697906911373
   onnx-file=/home/<user>/models/peoplenet/resnet34_peoplenet_int8.onnx
   int8-calib-file=/home/<user>/models/peoplenet/resnet34_peoplenet_int8.txt
   model-engine-file=/home/<user>/models/peoplenet/peoplenet_b1_gpu0_int8.engine
   labelfile-path=/home/<user>/models/peoplenet/labels.txt
   infer-dims=3;544;960
   batch-size=1
   network-mode=1          ; 0=FP32 1=INT8 2=FP16
   num-detected-classes=3  ; person, bag, face
   interval=0
   gie-unique-id=1
   cluster-mode=2
   output-blob-names=output_bbox/BiasAdd:0;output_cov/Sigmoid:0

   [class-attrs-all]
   pre-cluster-threshold=0.4
   topk=20
   nms-iou-threshold=0.5

   ; Ignore bags (class 1) and faces (class 2) — count people only
   [class-attrs-1]
   pre-cluster-threshold=1.1
   [class-attrs-2]
   pre-cluster-threshold=1.1
   ```
   **Deleted vs. the old repo:** `tlt-model-key`, `tlt-encoded-model`. Those are dead. If you copy their config verbatim it will not build.

4. **Smoke test with gst-launch** before writing any app code:
   ```bash
   gst-launch-1.0 v4l2src device=/dev/video0 ! \
     image/jpeg,width=1280,height=720,framerate=30/1 ! jpegdec ! videoconvert ! \
     nvvideoconvert ! 'video/x-raw(memory:NVMM),format=NV12' ! \
     m.sink_0 nvstreammux name=m batch-size=1 width=1280 height=720 live-source=1 ! \
     nvinfer config-file-path=./config_infer_peoplenet.txt ! \
     nvvideoconvert ! nvdsosd ! nv3dsink
   ```

**Checkpoint:** boxes around people, live, from your webcam. Note your FPS — aim for 25–30.

---

## Phase 4 — Tracking (Week 2–3)

Counting requires persistent IDs, so detection alone isn't enough.

Add to the pipeline after `nvinfer`:
```
nvtracker tracker-width=640 tracker-height=384 \
  ll-lib-file=/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so \
  ll-config-file=/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app/config_tracker_NvDCF_perf.yml
```
Start with `NvDCF_perf`. If IDs swap when people cross paths, move to `config_tracker_NvDCF_accuracy.yml` and check your FPS cost.

**Checkpoint:** each person keeps the same ID number while walking across the frame.

---

## Phase 5 — The actual counting (Week 3) ⭐

This is the core of the project. Create `config_nvdsanalytics.txt`:

```ini
[property]
enable=1
config-width=1280
config-height=720
osd-mode=2
display-font-size=12

## Occupancy: how many people are inside the room region
[roi-filtering-stream-0]
enable=1
roi-RoomArea=50;50;1230;50;1230;670;50;670
inverse-roi=0
class-id=0

## Entry/exit: a line across the doorway
[line-crossing-stream-0]
enable=1
## label;direction-x1,y1;direction-x2,y2;line-x1,y1;line-x2,y2
line-crossing-Entry=580;400;620;700;450;500;790;500
line-crossing-Exit=620;700;580;400;450;500;790;500
class-id=0
extended=0
mode=loose

[overcrowding-stream-0]
enable=1
roi-RoomArea=50;50;1230;50;1230;670;50;670
object-threshold=20
```

**How to read line-crossing:** the first coordinate pair is a *direction vector* (which way counts as a crossing), the second pair is the *line segment* itself. Entry and Exit are the same line with reversed direction vectors. Get the pixel coordinates by screenshotting a frame from your mounted camera and reading them off in any image editor.

Insert `nvdsanalytics config-file=config_nvdsanalytics.txt` between `nvtracker` and `nvvideoconvert`.

**Reading the results in Python** — attach a probe to the `nvdsanalytics` src pad:
```python
frame_meta.frame_user_meta_list → NVDS_USER_FRAME_META_NVDSANALYTICS
  → NvDsAnalyticsFrameMeta:
       objInROIcnt["RoomArea"]   # current occupancy
       objLCCumCnt["Entry"]      # cumulative entries
       objLCCumCnt["Exit"]       # cumulative exits
       ocStatus["RoomArea"]      # overcrowding flag
```
`deepstream_python_apps/apps/deepstream-nvdsanalytics/` has a working reference for this exact metadata parsing — clone it and adapt rather than starting blank.

**Checkpoint:** walk in and out of frame; counters increment correctly. Do this ~20 times and record accuracy — this number goes in your report.

---

## Phase 6 — Data layer (Week 3–4)

Keep it boring. In your probe callback:

1. **Throttle** — write once per second, not per frame.
2. **SQLite schema:**
   ```sql
   CREATE TABLE occupancy_log (
     ts          DATETIME DEFAULT CURRENT_TIMESTAMP,
     room_id     TEXT,
     occupancy   INTEGER,   -- objInROIcnt
     entries_cum INTEGER,
     exits_cum   INTEGER,
     fps         REAL
   );
   CREATE TABLE events (
     ts DATETIME DEFAULT CURRENT_TIMESTAMP,
     room_id TEXT, event_type TEXT, object_id INTEGER
   );
   ```
3. **Reconciliation logic** — worth doing, and a good talking point for your report: ROI count is instantaneous truth but misses occluded people; `entries − exits` is cumulative but drifts as errors accumulate. Use ROI count as the primary display, and flag when `|ROI − (entries − exits)| > threshold` as a confidence warning. Reset the cumulative baseline when the room is verified empty.

---

## Phase 7 — Dashboard (Week 4, parallel with Phases 5–6)

Two people can build this against a **fake data generator** starting in week 2 — don't block on the pipeline being finished.

**Backend** — FastAPI on the Jetson:
```
GET  /api/current              → {occupancy, capacity, status, last_updated}
GET  /api/history?hours=24     → time-series for charts
GET  /api/stats/daily          → peak hour, avg occupancy, total visitors
WS   /ws/live                  → push updates every second
```

**Frontend** — what to actually show:
- Big current-occupancy number with a color state (green / amber / red vs. capacity)
- Occupancy over time (line chart, last 24h)
- Entries vs. exits per hour (bar chart)
- Peak-hours heatmap by day of week
- "Busiest time to avoid" callout — this is the user-facing value, lead with it

Serve the built frontend as static files from FastAPI so it's one process. Access at `http://<jetson-ip>:8000` from any laptop on the network.

---

## Phase 8 — Demo hardening (Final week)

- `systemd` service so the pipeline auto-starts on boot — do **not** demo from a terminal you have to babysit.
- Camera mounting: a high corner angle beats eye level. Mount it where you'll demo, and re-derive your ROI/line coordinates there. Coordinates are scene-specific.
- Test under the actual demo lighting. PeopleNet degrades in low light.
- Record a fallback video of the working system.
- Log FPS and accuracy numbers — you need them for the report regardless.

---

## Suggested split for 4 people

| Person | Owns |
|---|---|
| A | Jetson flashing, DeepStream install, keeps the device healthy (Phases 1–2), then pipeline tuning |
| B | Pipeline + model + tracker + nvdsanalytics config (Phases 3–5) |
| C | Probe → SQLite → FastAPI backend (Phase 6) |
| D | Dashboard frontend (Phase 7) — starts week 2 against mock JSON |

A and B pair heavily early; C and D work in parallel on fake data. Everyone converges in the final week on integration and accuracy testing.

---

## Rough timeline to a first demo (~4 weeks)

| Week | Goal |
|---|---|
| 1 | Jetson flashed, DeepStream sample running, C920 verified |
| 2 | PeopleNet detecting live from webcam at usable FPS; dashboard mockup built on fake data |
| 3 | Tracker + nvdsanalytics counting entries/exits/occupancy; SQLite logging |
| 4 | API + real dashboard wired up; accuracy testing; auto-start service; demo rehearsal |

---

## Known traps

1. **Copying the old repo's `nvinfer` config verbatim.** The `.etlt` fields are dead. Use `onnx-file=`.
2. **First engine build looks like a hang.** TensorRT takes 3–10 minutes the first time. Let it finish; it caches after that.
3. **Camera format.** Ask for MJPEG explicitly or you'll get 10fps and blame the model.
4. **Coordinates are resolution-specific.** `config-width`/`config-height` in the analytics config must match the streammux resolution, or your lines land in the wrong place.
5. **Counting a crowd exiting at once.** People occlude each other at a doorway. Your accuracy number will be lower for groups than for individuals — measure both and report honestly. It's a better report than pretending it's perfect.
6. **Don't add Kafka.** The reference repo uses it for a multi-building deployment. You have one camera and one room.

---

## Useful references

- DeepStream install: `docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_Installation.html`
- `Gst-nvdsanalytics` plugin docs (config key reference): `docs.nvidia.com/metropolis/deepstream/dev-guide/text/DS_plugin_gst-nvdsanalytics.html`
- Python bindings + samples: `github.com/NVIDIA-AI-IOT/deepstream_python_apps`
- PeopleNet model card: NGC catalog → `nvidia/tao/peoplenet`
- Original repo (use for logic reference only): `github.com/NVIDIA-AI-IOT/deepstream-occupancy-analytics`
