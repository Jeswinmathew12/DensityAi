"""Sends occupancy counts from the DeepStream pipeline to the DensityAI backend.

Usage inside the nvdsanalytics pad probe (see occupancy-tracker-plan.md, Phase 5):

    from probe_client import ProbeClient
    client = ProbeClient("http://localhost:8000", token=os.environ.get("INGEST_TOKEN"))

    # per frame, after reading NvDsAnalyticsFrameMeta:
    client.send_snapshot("cam-1",
                         occupancy=meta.objInROIcnt["RoomArea"],
                         entries_cum=meta.objLCCumCnt["Entry"],
                         exits_cum=meta.objLCCumCnt["Exit"],
                         fps=current_fps)

send_snapshot() never blocks the pipeline: it throttles to one sample per second per
camera and hands off to a background thread. If the backend is down, samples are kept
(up to ~5 minutes' worth) and sent when it comes back. Only numbers leave the Jetson,
never frames. Stdlib only, so there's nothing extra to install.
"""
import json
import threading
import time
import urllib.request


class ProbeClient:
    def __init__(self, url="http://localhost:8000", token=None, interval=1.0, max_pending=300):
        self.url = url.rstrip("/") + "/api/ingest"
        self.token = token
        self.interval = interval
        self.max_pending = max_pending
        self.last_sent = {}
        self.pending = []
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self._run, name="densityai-sender", daemon=True).start()

    def send_snapshot(self, camera_id, occupancy, entries_cum, exits_cum, fps=None):
        now = time.time()
        if now - self.last_sent.get(camera_id, 0) < self.interval:
            return
        self.last_sent[camera_id] = now
        sample = {
            "cameraId": camera_id, "ts": now, "occupancy": int(occupancy),
            "entriesCum": int(entries_cum), "exitsCum": int(exits_cum), "fps": fps,
        }
        with self.lock:
            self.pending.append(sample)
            del self.pending[:-self.max_pending]  # drop the oldest if the backend has been down a while
        self.wake.set()

    def _run(self):
        while True:
            self.wake.wait()
            self.wake.clear()
            with self.lock:
                batch, self.pending = self.pending, []
            if not batch:
                continue
            try:
                self._post(batch)
            except Exception as e:
                with self.lock:
                    self.pending = (batch + self.pending)[-self.max_pending:]
                print(f"[probe_client] backend unreachable ({e}); holding {len(self.pending)} samples")
                time.sleep(2)
                self.wake.set()  # try again

    def _post(self, batch):
        sent_at = time.time()  # lets the backend correct for the Jetson's clock being off
        body = [dict(s, sentAt=sent_at) for s in batch]
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["X-Ingest-Token"] = self.token
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=5).close()
