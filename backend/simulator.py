"""Fake Jetson: posts counts to the backend exactly like the real DeepStream probe will.

    python backend/simulator.py                  # every camera in zones.json, real time
    python backend/simulator.py --hour 14        # start the simulated day at 2 PM
    python backend/simulator.py --speed 60       # one simulated minute per real second
    python backend/simulator.py --dropout 0.02   # 2% chance per second of a camera going silent

Stdlib only, so it runs without installing anything.
"""
import argparse
import json
import math
import os
import random
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ZONES_PATH = Path(__file__).resolve().parent / "zones.json"


def day_curve(hour):
    """0..1 peaking mid-afternoon; same curve as dayCurve() in fakeDataGenerator.js,
    with a small floor so testing at night still shows a few people."""
    return max(0.1, math.sin((hour - 7) / 12 * math.pi))


def poisson(lam):
    """Random count of arrivals for an average of `lam` (Knuth's method; fine for small lam)."""
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= random.random()
        if p <= limit:
            return k
        k += 1


class Camera:
    """One camera's view of a room: a true head count, plus detector noise on the ROI count."""

    def __init__(self, camera_id, capacity, hour):
        self.id = camera_id
        self.capacity = capacity
        self.true = round(capacity * 0.8 * day_curve(hour))
        self.entries_cum = self.true  # everyone already inside "walked in" before we started
        self.exits_cum = 0
        self.silent_until = 0

    def step(self, hour, dt):
        """Advance `dt` simulated seconds. Returns the ROI count the detector would report."""
        target = self.capacity * 0.8 * day_curve(hour)
        # Close the gap to the target over ~10 simulated minutes, rounding randomly so small
        # steps still happen.
        move = math.floor((target - self.true) * min(1.0, dt / 600) + random.random())
        churn = poisson(0.0005 * self.capacity * dt)  # people passing through in both directions
        entries = churn + max(move, 0)
        exits = min(churn + max(-move, 0), self.true + entries)
        self.true += entries - exits
        self.entries_cum += entries
        self.exits_cum += exits

        if random.random() < 0.03:  # occasional occlusion: a few people briefly hidden
            return max(0, self.true - random.randint(2, 4))
        return max(0, self.true + random.choice((-1, 0, 0, 0, 0, 1)))


def post(url, token, sample):
    req = urllib.request.Request(
        f"{url}/api/ingest",
        data=json.dumps(sample).encode(),
        headers={"Content-Type": "application/json", **({"X-Ingest-Token": token} if token else {})},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=3).close()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default=os.environ.get("DENSITY_API_URL", "http://localhost:8000"))
    parser.add_argument("--cameras", help="comma-separated camera ids (default: all in zones.json)")
    parser.add_argument("--hour", type=float, help="simulated hour of day to start at (default: now)")
    parser.add_argument("--speed", type=float, default=1, help="simulated seconds per real second")
    parser.add_argument("--dropout", type=float, default=0, help="chance per second of a camera going silent for 15-30 s")
    args = parser.parse_args()

    config = json.loads(ZONES_PATH.read_text())
    capacity = {z["id"]: z["capacity"] for z in config["zones"]}
    per_zone = {}
    for c in config["cameras"]:
        per_zone[c["zoneId"]] = per_zone.get(c["zoneId"], 0) + 1
    wanted = set(args.cameras.split(",")) if args.cameras else None

    now = datetime.now()
    sim_hour = args.hour if args.hour is not None else now.hour + now.minute / 60
    # With "sum" fusion each camera covers a share of the room, so split the capacity between them.
    cameras = [
        Camera(c["id"], max(1, capacity[c["zoneId"]] // per_zone[c["zoneId"]]), sim_hour)
        for c in config["cameras"]
        if wanted is None or c["id"] in wanted
    ]
    token = os.environ.get("INGEST_TOKEN")
    print(f"Simulating {', '.join(c.id for c in cameras)} -> {args.url} (speed x{args.speed:g}). Ctrl+C to stop.")

    backend_up = True
    while True:
        tick = time.time()
        sim_hour = (sim_hour + args.speed / 3600) % 24
        for cam in cameras:
            roi = cam.step(sim_hour, args.speed)
            if tick < cam.silent_until:
                continue
            if random.random() < args.dropout:
                cam.silent_until = tick + random.uniform(15, 30)
                print(f"{cam.id}: going silent for a bit")
                continue
            sample = {
                "cameraId": cam.id, "ts": tick, "sentAt": time.time(), "occupancy": roi,
                "entriesCum": cam.entries_cum, "exitsCum": cam.exits_cum, "fps": round(random.uniform(26, 30), 1),
            }
            try:
                post(args.url, token, sample)
                if not backend_up:
                    print("Backend is back.")
                backend_up = True
            except urllib.error.HTTPError as e:
                raise SystemExit(f"Backend rejected sample ({e.code}): {e.read().decode()}")
            except OSError:
                if backend_up:
                    print(f"Can't reach {args.url}, retrying every second...")
                backend_up = False
        time.sleep(max(0, 1 - (time.time() - tick)))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
