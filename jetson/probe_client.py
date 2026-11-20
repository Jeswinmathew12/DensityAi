"""Sends occupancy counts from the DeepStream pipeline to the DensityAI collector.

Usage inside the nvdsanalytics pad probe (see occupancy-tracker-plan.md, Phase 5):

    from probe_client import ProbeClient
    client = ProbeClient("http://localhost:8001", token=os.environ.get("INGEST_TOKEN"))

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


class DwellTracker:
    """Time each tracked person spends in the zone, from the tracker's object ids.

    Call update() once per frame with the ids currently inside the zone. A person who has not
    been seen for `gone_after` seconds has left; update() returns how long each such person
    stayed. Brief misses (occlusion, a dropped detection) don't end the visit.
    """

    def __init__(self, gone_after=2.0, min_dwell=1.0):
        self.gone_after = gone_after
        self.min_dwell = min_dwell
        self.first = {}
        self.last = {}

    def update(self, ids, now):
        for i in ids:
            self.first.setdefault(i, now)
            self.last[i] = now
        done = []
        for i, seen in list(self.last.items()):
            if now - seen > self.gone_after:
                stayed = seen - self.first.pop(i)
                del self.last[i]
                if stayed >= self.min_dwell:
                    done.append(round(stayed, 1))
        return done


class ProbeClient:
    def __init__(self, url="http://localhost:8001", token=None, interval=1.0, max_pending=300):
        self.url = url.rstrip("/") + "/api/ingest"
        self.token = token
        self.interval = interval
        self.max_pending = max_pending
        self.last_sent = {}
        self.dwell = {}  # camera_id -> finished visits not sent yet (seconds each)
        self.pending = []
        self.lock = threading.Lock()
        self.wake = threading.Event()
        threading.Thread(target=self._run, name="densityai-sender", daemon=True).start()

    def add_dwell(self, camera_id, seconds):
        """Queue finished visits (seconds each); they go out with the camera's next sample."""
        if seconds:
            self.dwell.setdefault(camera_id, []).extend(seconds)

    def send_snapshot(self, camera_id, occupancy, entries_cum, exits_cum, fps=None):
        now = time.time()
        if now - self.last_sent.get(camera_id, 0) < self.interval:
            return
        self.last_sent[camera_id] = now
        sample = {
            "cameraId": camera_id, "ts": now, "occupancy": int(occupancy),
            "entriesCum": int(entries_cum), "exitsCum": int(exits_cum), "fps": fps,
        }
        dwell = self.dwell.pop(camera_id, None)
        if dwell:
            sample["dwell"] = dwell
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
