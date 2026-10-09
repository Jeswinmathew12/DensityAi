"""Turns raw per-camera counts into the per-zone numbers the dashboard shows.

No I/O here, so everything is easy to unit test.
"""
from collections import deque
from datetime import datetime, timezone
from statistics import median

# Median of the last 5 samples (~5 s at 1 Hz) hides single-frame flicker and brief occlusions.
SMOOTH_WINDOW = 5
# A camera that hasn't posted for this long is treated as offline.
STALE_AFTER_S = 10


def smooth(values):
    """Rolling median of recent counts, rounded to a whole person."""
    return int(median(values) + 0.5) if values else 0


def fuse(counts, mode):
    """Combine camera counts for one zone.

    "sum": cameras cover separate parts of the zone.
    "max": cameras overlap, so the one that sees the most people wins.
    """
    if not counts:
        return 0
    return max(counts) if mode == "max" else sum(counts)


def zone_is_stale(camera_stale, mode):
    """With "sum", one dead camera makes the total wrong. With "max", the others still cover the zone."""
    if not camera_stale:
        return True
    return any(camera_stale) if mode == "sum" else all(camera_stale)


def correct_ts(ts, sent_at, received_at):
    """Map a sample's Jetson-clock timestamp onto the backend clock.

    The probe stamps each sample with `ts` when it was counted and `sentAt` when the
    request went out. The gap between `sentAt` and our receive time is the Jetson's
    clock error, which also stays correct for samples buffered during an outage.
    """
    if ts is None:
        return received_at
    if sent_at is None:
        return ts
    return ts + (received_at - sent_at)


def iso(ts):
    """Epoch seconds to the same ISO format as JS Date.toISOString()."""
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class LiveState:
    """Latest counts per camera, rolled up into the zones shape from fakeDataGenerator.js."""

    def __init__(self, config):
        self.zones = config["zones"]
        self.camera_zone = {c["id"]: c["zoneId"] for c in config["cameras"]}
        self.recent = {cid: deque(maxlen=SMOOTH_WINDOW) for cid in self.camera_zone}
        self.last_seen = {}
        self.fps = {}

    def add(self, camera_id, occupancy, received_at, fps=None):
        # After an outage, start the median fresh so counts from before it don't leak in.
        if self.camera_stale(camera_id, received_at):
            self.recent[camera_id].clear()
        self.recent[camera_id].append(occupancy)
        self.last_seen[camera_id] = received_at
        if fps is not None:
            self.fps[camera_id] = fps

    def camera_stale(self, camera_id, now):
        seen = self.last_seen.get(camera_id)
        return seen is None or now - seen > STALE_AFTER_S

    def zones_snapshot(self, now):
        out = []
        for z in self.zones:
            cams = [cid for cid, zid in self.camera_zone.items() if zid == z["id"]]
            mode = z.get("fusion", "sum")
            stale = [self.camera_stale(cid, now) for cid in cams]
            # For "max", ignore offline cameras so a dead one can't pin the count.
            live = [cid for cid, s in zip(cams, stale) if mode == "sum" or not s]
            seen = [self.last_seen[cid] for cid in cams if cid in self.last_seen]
            out.append({
                "id": z["id"],
                "name": z["name"],
                "capacity": z["capacity"],
                "cameras": len(cams),
                "occupancy": fuse([smooth(self.recent[cid]) for cid in live], mode),
                "lastUpdated": iso(max(seen)) if seen else None,
                "stale": zone_is_stale(stale, mode),
            })
        return out

    def cameras_snapshot(self, now):
        return [
            {
                "id": cid,
                "zoneId": zid,
                "lastSeen": iso(self.last_seen.get(cid)),
                "fps": self.fps.get(cid),
                "stale": self.camera_stale(cid, now),
            }
            for cid, zid in self.camera_zone.items()
        ]
