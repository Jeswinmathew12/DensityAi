#!/usr/bin/env python3
"""DensityAI occupancy pipeline for the Jetson (DeepStream 7.1, pyds 1.2.0).

USB camera -> PeopleNet -> [tracker] -> nvdsanalytics (ROI count) -> probe -> backend.

    python3 jetson/occupancy_pipeline.py
    python3 jetson/occupancy_pipeline.py --no-display          # headless (SSH, systemd)
    python3 jetson/occupancy_pipeline.py --tracker             # needed for line crossing

Run with the system python3 (where pyds and gi are installed), not backend/.venv.
Only counts leave the Jetson, never frames.

Metadata parsing follows NVIDIA's deepstream_python_apps v1.2.0
apps/deepstream-nvdsanalytics, and camera input follows apps/deepstream-test1-usbcam.
"""
import argparse
import os
import signal
import sys
import time

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # noqa: E402

import pyds  # noqa: E402

from probe_client import ProbeClient  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TRACKER_DIR = "/opt/nvidia/deepstream/deepstream/samples/configs/deepstream-app"
TRACKER_LIB = "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so"
TRACKER_CONFIG = os.path.join(TRACKER_DIR, "config_tracker_NvDCF_perf.yml")

# Must match config-width/config-height in config_nvdsanalytics.txt.
WIDTH, HEIGHT, FPS = 1280, 720, 30
ROI_NAME = "RoomArea"
ENTRY_NAME, EXIT_NAME = "Entry", "Exit"


class FpsCounter:
    """Counts frames and reports the rate once per interval."""

    def __init__(self, interval=1.0):
        self.interval = interval
        self.start = time.monotonic()
        self.frames = 0
        self.fps = None  # None until the first full interval has passed

    def tick(self):
        """Call once per frame. Returns True when self.fps was just refreshed."""
        self.frames += 1
        now = time.monotonic()
        elapsed = now - self.start
        if elapsed < self.interval:
            return False
        self.fps = self.frames / elapsed
        self.start, self.frames = now, 0
        return True


def make(factory, name):
    element = Gst.ElementFactory.make(factory, name)
    if not element:
        sys.exit(f"Could not create GStreamer element '{factory}'. Is DeepStream 7.1 installed?")
    return element


def make_nvvideoconvert(name):
    conv = make("nvvideoconvert", name)
    # REQUIRED on EVERY nvvideoconvert: DeepStream 7.1 on JetPack 6.2 crashes with
    # "Failed in mem copy" / cudaErrorIllegalAddress after ~2 minutes without it.
    conv.set_property("copy-hw", 2)
    return conv


def make_caps(name, caps):
    f = make("capsfilter", name)
    f.set_property("caps", Gst.Caps.from_string(caps))
    return f


def on_bus_message(bus, message, loop):
    t = message.type
    if t == Gst.MessageType.EOS:
        print("End of stream")
        loop.quit()
    elif t == Gst.MessageType.WARNING:
        err, debug = message.parse_warning()
        print(f"Warning: {err}: {debug}", file=sys.stderr)
    elif t == Gst.MessageType.ERROR:
        err, debug = message.parse_error()
        print(f"Error: {err}: {debug}", file=sys.stderr)
        loop.quit()
    return True


def make_analytics_probe(client, camera_id):
    """Builds the pad probe for the nvdsanalytics src pad."""
    meta_type = pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSFRAME.USER_META")
    fps_counter = FpsCounter()

    def probe(pad, info, _user_data):
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK
        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        if not batch_meta:
            return Gst.PadProbeReturn.OK

        l_frame = batch_meta.frame_meta_list
        while l_frame is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
            except StopIteration:
                break

            occupancy = entries = exits = 0
            l_user = frame_meta.frame_user_meta_list
            while l_user is not None:
                try:
                    user_meta = pyds.NvDsUserMeta.cast(l_user.data)
                except StopIteration:
                    break
                if user_meta.base_meta.meta_type == meta_type:
                    analytics = pyds.NvDsAnalyticsFrameMeta.cast(user_meta.user_meta_data)
                    occupancy = analytics.objInROIcnt.get(ROI_NAME, 0)
                    entries = analytics.objLCCumCnt.get(ENTRY_NAME, 0)
                    exits = analytics.objLCCumCnt.get(EXIT_NAME, 0)
                try:
                    l_user = l_user.next
                except StopIteration:
                    break

            refreshed = fps_counter.tick()
            # Throttles to 1 Hz and never blocks, so calling it every frame is fine.
            client.send_snapshot(camera_id, occupancy, entries, exits, fps_counter.fps)
            if refreshed:
                print(f"[{camera_id}] people in {ROI_NAME}: {occupancy}   FPS: {fps_counter.fps:.1f}")

            try:
                l_frame = l_frame.next
            except StopIteration:
                break
        return Gst.PadProbeReturn.OK

    return probe


def build_pipeline(args):
    pipeline = Gst.Pipeline()

    source = make("v4l2src", "usb-cam")
    source.set_property("device", args.device)
    caps_jpeg = make_caps("jpeg-caps", f"image/jpeg,width={WIDTH},height={HEIGHT},framerate={FPS}/1")
    jpegdec = make("jpegdec", "jpeg-decoder")
    videoconvert = make("videoconvert", "videoconvert")
    conv_in = make_nvvideoconvert("nvconv-in")
    caps_nvmm = make_caps("nvmm-caps", "video/x-raw(memory:NVMM),format=NV12")

    streammux = make("nvstreammux", "stream-muxer")
    streammux.set_property("batch-size", 1)
    streammux.set_property("width", WIDTH)
    streammux.set_property("height", HEIGHT)
    streammux.set_property("live-source", 1)
    streammux.set_property("batched-push-timeout", 4000000)

    pgie = make("nvinfer", "peoplenet")
    pgie.set_property("config-file-path", args.infer_config)

    tracker = None
    if args.tracker:
        tracker = make("nvtracker", "tracker")
        tracker.set_property("tracker-width", 640)
        tracker.set_property("tracker-height", 384)
        tracker.set_property("ll-lib-file", TRACKER_LIB)
        tracker.set_property("ll-config-file", TRACKER_CONFIG)

    analytics = make("nvdsanalytics", "analytics")
    analytics.set_property("config-file", args.analytics_config)

    conv_out = make_nvvideoconvert("nvconv-out")
    osd = make("nvdsosd", "osd")
    if args.no_display:
        sink = make("fakesink", "sink")
    else:
        sink = make("nv3dsink", "sink")
    sink.set_property("sync", False)

    chain = [source, caps_jpeg, jpegdec, videoconvert, conv_in, caps_nvmm]
    rest = [pgie] + ([tracker] if tracker else []) + [analytics, conv_out, osd, sink]
    for element in chain + [streammux] + rest:
        pipeline.add(element)

    for a, b in zip(chain, chain[1:]):
        if not a.link(b):
            sys.exit(f"Could not link {a.get_name()} to {b.get_name()}")

    request_pad = getattr(streammux, "request_pad_simple", None) or streammux.get_request_pad
    sinkpad = request_pad("sink_0")
    if not sinkpad:
        sys.exit("Could not get sink_0 pad from nvstreammux")
    if caps_nvmm.get_static_pad("src").link(sinkpad) != Gst.PadLinkReturn.OK:
        sys.exit("Could not link the camera chain to nvstreammux")

    for a, b in zip([streammux] + rest, rest):
        if not a.link(b):
            sys.exit(f"Could not link {a.get_name()} to {b.get_name()}")

    return pipeline, analytics


def parse_args():
    p = argparse.ArgumentParser(description="DensityAI occupancy pipeline (DeepStream 7.1)")
    p.add_argument("--camera-id", default="cam-1", help="must be listed in backend/zones.json")
    p.add_argument("--device", default="/dev/video0", help="V4L2 camera device")
    p.add_argument("--infer-config",
                   default=os.path.expanduser("~/models/peoplenet/config_infer_peoplenet.txt"),
                   help="nvinfer config for PeopleNet")
    p.add_argument("--analytics-config", default=os.path.join(HERE, "config_nvdsanalytics.txt"),
                   help="nvdsanalytics config (ROI and line crossing)")
    p.add_argument("--tracker", action="store_true", help="add nvtracker (needed for line crossing)")
    p.add_argument("--no-display", action="store_true", help="use fakesink instead of a window")
    return p.parse_args()


def main():
    args = parse_args()
    for label, path in (("--infer-config", args.infer_config),
                        ("--analytics-config", args.analytics_config)):
        if not os.path.isfile(path):
            sys.exit(f"{label} file not found: {path}")

    api_url = os.environ.get("DENSITY_API_URL", "http://localhost:8000")
    client = ProbeClient(api_url, token=os.environ.get("INGEST_TOKEN"))
    print(f"Sending counts for {args.camera_id} to {api_url}")

    Gst.init(None)
    pipeline, analytics = build_pipeline(args)

    analytics.get_static_pad("src").add_probe(
        Gst.PadProbeType.BUFFER, make_analytics_probe(client, args.camera_id), None)

    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", on_bus_message, loop)

    # Ctrl+C (and SIGTERM, for systemd) stop the loop so we can shut the pipeline down cleanly.
    for sig in (signal.SIGINT, signal.SIGTERM):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, loop.quit)

    print("Starting pipeline. The first run builds a TensorRT engine, which can take several minutes.")
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    finally:
        print("Stopping pipeline")
        pipeline.set_state(Gst.State.NULL)
        bus.remove_signal_watch()


if __name__ == "__main__":
    main()
