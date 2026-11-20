# DensityAI Dashboard

A web dashboard for real-time room occupancy monitoring, built for our NC State senior design project.

## Background

DensityAI is an AI camera-based occupancy monitoring system. Cameras feed a person-detection model (NVIDIA PeopleNet running on a Jetson Orin Nano), and this dashboard shows how busy each room or zone is, both live and over time.

The main goal of the UI is to answer **"how busy is it right now?"** at a glance. Trends and planning data are secondary and should never crowd out the live view.

### System overview

```
Camera -> Jetson Orin Nano, JetPack 6.2.1 + DeepStream 7.1 (PeopleNet + tracker + nvdsanalytics)
       -> collector (backend/app/collector.py, port 8001): turns counts into rows in PostgreSQL
       -> PostgreSQL `events` table (TimescaleDB hypertable if installed)
       -> web service (backend/app/main.py, port 8000): REST API + live WebSocket, reads only the database
       -> React dashboard (this repo): talks only to the web service, never to the Jetson
```

The Jetson pipeline is planned in [occupancy-tracker-plan.md](occupancy-tracker-plan.md). The collector and web service are two separate programs that share only the database, so in a real store the Jetson stays on site and the rest can run on a server. Until the Jetson pipeline is running, `backend/simulator.py` stands in for it. The dashboard can also run on its own with mock data.

### Milestones

| Demo | Date | Scope |
|---|---|---|
| Demo 1 (proof of concept) | Oct 12-15 | Single camera, one zone, live count |
| Demo 2 (Design Day) | Dec 1 | Two zones, multiple cameras, full dashboard with history and trends |

### Features

- Pages via the sidebar: Dashboard, Zones, Trends, Store insights, System, Settings, Admin
- Store insights: busiest-times heatmap, visitors by weekday and hour, where shoppers go (pie), how long they stay (pie), zone scorecard, crowding alerts and recommended actions. Comes with a sample store (`npm run mock-store`)
- System: each hop from camera to dashboard with a live status, plus the REST API
- Live occupancy count with a status color: green = Available, blue = Moderate, red = Busy
- 24-hour occupancy trend
- Per-zone table with count, capacity and status
- Bidirectional in/out traffic chart
- Insights panel

Status thresholds are under 50% Available, 50-75% Moderate and over 75% Busy. They are defined in one place, `src/utils/status.js`.

## Tech stack

- **React 18**, plain JavaScript (no TypeScript)
- **Create React App** (`react-scripts` 5) for build tooling
- **Recharts** for charts
- **lucide-react** for icons
- **Plain CSS** with CSS variables in `src/App.css` (no Tailwind, no CSS-in-JS)

### Dependencies

| Package | Version | Purpose |
|---|---|---|
| react, react-dom | ^18.3.1 | UI framework |
| react-scripts | 5.0.1 | Dev server, build, test runner |
| recharts | ^2.15.4 | Charts |
| lucide-react | ^0.400.0 | Icons |

## Project structure

```
public/index.html              HTML entry
src/index.js                   React bootstrap
src/App.jsx                    Layout + sidebar nav; picks the page from the URL hash
src/pages/                     Dashboard, Zones, Trends, Settings, Admin pages
src/App.css                    All styles + CSS variables
src/hooks/useOccupancyData.js  Data-access layer: mock generators or live backend
src/hooks/useHashRoute.js      Tiny hash router (no react-router dependency)
src/services/api.js            Backend URL + WebSocket client
src/utils/fakeDataGenerator.js Mock data for all dashboard sections
src/utils/status.js            Shared status helper (thresholds live here only)
src/components/                KpiCards, SeatStrip, StatRow, OccupancyTrend, ZoneTable, TrafficChart, Insights
backend/app/collector.py       Collector: takes the Jetson's counts, writes events to PostgreSQL
backend/app/main.py            Web service: REST API + live WebSocket, reads PostgreSQL
backend/app/analytics.py       Store insights (busiest times, dwell, recommendations) from events
backend/app/db.py              PostgreSQL schema (sites, zones, cameras, events) and queries
backend/mock_store.py          Weeks of sample data for a fictional store
backend/                       Also the simulator, setup scripts and tests
docs/jetson-setup.md           Jetson setup runbook and known issues
docs/demo-day.md               Design Day talking points (business plan, future plans)
jetson/setup_peoplenet.sh      Downloads PeopleNet and writes its nvinfer config
jetson/occupancy_pipeline.py   DeepStream pipeline: camera -> PeopleNet -> ROI count -> backend
jetson/config_nvdsanalytics.txt ROI and line-crossing config for the pipeline
jetson/probe_client.py         Sender the DeepStream probe calls on the Jetson
```

### Data

The shapes returned by `src/utils/fakeDataGenerator.js` are the data contract, and the backend returns the same shapes. `useOccupancyData.js` is the only file that knows whether data is mock or live.

## Backend

```
Jetson probe / simulator --POST /api/ingest--> collector :8001 --> PostgreSQL events
                                                                     |
dashboard <--REST + /ws/live-- web service :8000 <--reads every second+
```

- **Database:** PostgreSQL (`npm run db:setup` installs it; `-- --timescale` adds TimescaleDB). One simple `events` table holds everything: `time, site_id, zone_id, camera_id, kind, value, detail`, where `kind` is `occupancy` (people in the zone), `entry`, `exit` (people crossing the line), `dwell` (seconds one person spent in the zone) or `alert` (zone crowded). `sites`, `zones` and `cameras` describe where events come from. `DATABASE_URL` picks the database (default `postgresql:///densityai`, the local socket with no password).
- **What the Jetson sends:** numbers only, never images. One JSON object per camera per second, or an array of them:
  ```json
  { "cameraId": "cam-1", "ts": 1759500000.0, "sentAt": 1759500000.2,
    "occupancy": 12, "entriesCum": 140, "exitsCum": 128, "fps": 27.4 }
  ```
  `occupancy` is the `nvdsanalytics` ROI count, and `entriesCum`/`exitsCum` are its cumulative line-crossing counts (the collector turns them into `entry`/`exit` events). With `--tracker`, an optional `"dwell": [42.5, 7.0]` lists how many seconds each person who just left the zone spent in it. `ts` is when the frame was counted and `sentAt` is when the request went out. The backend uses the gap to correct for the Jetson's clock being wrong. If `INGEST_TOKEN` is set, requests must send it as `X-Ingest-Token`.
- **Collector** (`POST /api/ingest`, `POST /api/events` for ready-made events, `GET /api/health`): stores every sample, and writes an `alert` event when a zone reaches its `alertAt` level in `backend/zones.json` (at most once per 10 minutes).
- **Processing:**
  - The live count is the median of each camera's last 5 samples, which hides flicker and brief occlusions.
  - Cameras are combined per zone, using `"fusion": "sum"` (separate areas) or `"max"` (overlapping views) in `backend/zones.json`.
  - A zone is marked `stale` (shown as "Offline") when its cameras stop reporting for 10 seconds.
- **Web service endpoints** (interactive docs at http://localhost:8000/docs):
  - `GET /api/sites`: every site (the live camera site, sample stores) with its zones
  - `GET /api/sites/{id}/analytics?days=28`: Store insights, same shape as `generateStoreAnalytics()`
  - `GET /api/sites/{id}/events?kind=&zone=&since=&until=&limit=`: raw events, newest first
  - `GET /api/system`: health of each hop, for the System page
  - `GET /api/zones`: live zones, same shape as `generateZones()`
  - `GET /api/history`: last 24 local hours (trends, traffic) and today's stats and insights, built from stored samples. Same shapes as the mock generators, with `null` where there is no data, so a camera that was off shows as a gap, not 0.
  - `GET /api/health`: per-camera last-seen time and FPS
  - `GET /api/admin/cameras`, `GET /api/admin/preview/{cameraId}`: the Admin page's camera list and newest annotated JPEG frame. Need `X-Admin-Password`; return 404 when `ADMIN_PASSWORD` is unset (admin off) or there's no frame from the last 5 s
  - `WS /ws/live`: pushes `{ "type": "zones", "zones": [...] }` on connect and whenever counts change
  - `GET /`: the built dashboard, if a `build/` folder exists (see [Viewing on other devices](#viewing-on-other-devices))
- **Configuration:**
  - `backend/zones.json`: the live site, its zones, capacities (usable seats), optional `alertAt`, and which camera is in which zone. The collector copies it into the database at startup
  - Env vars: `INGEST_TOKEN`, `ADMIN_PASSWORD` (turns on the Admin page), `DENSITY_PREVIEW_DIR` (where the pipeline keeps preview frames, default `/dev/shm/densityai`), `DATABASE_URL` (default `postgresql:///densityai`), `DENSITY_STATIC` (dashboard build folder, default `build/`), `DENSITY_TZ` (time zone for hourly history, default `America/New_York`)
  - Frontend: `REACT_APP_API_URL`, for the dev server only. If unset, the dev server uses `http://localhost:8000` and a production build uses the address the page was loaded from. `npm run serve` always builds with it unset (and warns if a `.env` file sets it), so the dashboard works on whatever network the Jetson is on.

In live mode the dashboard loads `/api/history` on connect and every minute, so nothing on screen is simulated. A new database starts empty, and history is kept across camera and backend restarts.

## How to run

### Prerequisites

- [Node.js](https://nodejs.org/) (LTS recommended) and npm. On macOS: `brew install node`

### Steps

```bash
git clone https://github.com/Jeswinmathew12/DensityAi.git
cd DensityAi
git checkout dashboard      # dashboard code lives on this branch
npm install
npm start
```

Open http://localhost:3000. Live counts drift with new mock data every 3 seconds.

### With the backend (live data)

Needs Python 3.9+ and PostgreSQL. Use three terminals:

```bash
npm run db:setup        # once: installs PostgreSQL (Ubuntu/Jetson) and creates your database role
npm run backend:setup   # once: creates backend/.venv and installs FastAPI, psycopg etc.
npm run backend:sim     # terminal 1: collector :8001 + web service :8000, database densityai_sim
npm run simulate        # terminal 2: fake Jetson posting counts every second
npm run start:live      # terminal 3: dashboard using the web service
```

With the real Jetson, use `npm run backend` instead of `backend:sim`. Real history lives in the `densityai` database and simulated history in `densityai_sim` (created automatically), so the two never mix. The simulator refuses to post to a collector that is writing `densityai`.

For the Store insights page, fill the database with six weeks of a sample store: `npm run mock-store` (run it again any time; it replaces the previous sample data and ends at the current time). It is its own site, labeled as sample data, so it never mixes with the camera's counts.

To start the live camera's history over (for example before a demo), run `npm run backend:reset`. It moves the live site's events into a backup table (`events_backup_<date>`) rather than deleting them, and leaves the sample store alone.

Simulator options: `npm run simulate -- --hour 14` starts at 2 PM, `--speed 60` fast-forwards a minute per second, and `--dropout 0.02` makes cameras go silent now and then to test the offline state. On Windows, set `REACT_APP_DATA_SOURCE=live` in a `.env.local` file and use `npm start`, since the `start:live` script uses macOS/Linux syntax.

### Viewing on other devices

The backend can serve the dashboard itself, so anyone on the same network can open it in a browser with nothing to install. On the machine running the backend:

```bash
REACT_APP_API_URL= npm run build:live   # live-mode build with no fixed address (repeat after frontend changes)
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8000
hostname -I                             # this machine's IP addresses
```

Then on a phone or laptop, open `http://<one-of-those-ips>:8000` (http, not https). The page connects to the backend at the same address automatically. On the Jetson, `npm run serve` does all of this and prints the addresses for you.

- `--host 0.0.0.0` is required. `npm run backend` only accepts connections from the same machine.
- Leave `REACT_APP_API_URL` empty for this build. If it's set (for example in `.env`), that address is baked into the build and the dashboard breaks on any other network.
- Viewers must be on the same network. On campus, eduroam works; `ncsu-guest` may block device-to-device traffic. See [Reaching the Jetson on any network](#reaching-the-jetson-on-any-network).
- If the machine has a firewall, open port 8000 (for example `sudo ufw allow 8000`).

### Other commands

| Command | What it does |
|---|---|
| `npm start` | Dev server at http://localhost:3000 (mock data) |
| `npm run start:live` | Dev server using the backend |
| `npm run build` | Production build into `build/` (run this to check for errors) |
| `npm run build:live` | Production build using the backend, for serving from port 8000 |
| `npm test` | Run tests |
| `npm run db:setup` | Install PostgreSQL and create your database role (`-- --timescale` adds TimescaleDB) |
| `npm run backend` | Collector (:8001) and web service (:8000), reload on changes |
| `npm run serve` | Jetson: build if needed, collector + web service for all devices, pipeline with auto-restart |
| `npm run backend:sim` | Same, using the `densityai_sim` database, for the simulator |
| `npm run mock-store` | Six weeks of sample-store data for Store insights (`-- --weeks 10`) |
| `npm run simulate` | Fake Jetson (`npm run simulate -- --help` for options) |
| `npm run backend:reset` | Move the live site's events to a backup table so history starts empty |
| `npm run backend:test` | Backend tests |

## How to run on the Jetson

The Jetson already has everything installed. To rebuild one from scratch, follow [docs/jetson-setup.md](docs/jetson-setup.md).

### Normal use: the boot service

The Jetson runs DensityAI as a background service called `densityai`. It starts by itself whenever the Jetson powers on, so on demo day you only need to:

1. Power on the Jetson and wait about a minute.
2. Open the dashboard in a browser. **Nothing opens by itself**; type the address:
   - on the Jetson: `http://localhost:8000`
   - on a laptop or phone: one of the addresses the service prints at startup (`journalctl -u densityai | grep start`), or `http://<ip>:8000` with an IP from `hostname -I`. Which one works depends on the network; see [Reaching the Jetson on any network](#reaching-the-jetson-on-any-network).

The service runs the backend and the camera pipeline together, restarts the pipeline if the camera is unplugged or it crashes, and waits for the clock to sync after a power loss so counts aren't stamped 1970. It shows no camera window. Stopping it stops the dashboard too; history is kept in PostgreSQL, and the time it was off shows as a gap.

Install it once (already done on our Jetson):

```bash
sudo jetson/install-service.sh            # install, start now, and start at every boot
sudo jetson/install-service.sh --remove   # uninstall completely
```

Day-to-day commands:

| Command | What it does |
|---|---|
| `systemctl status densityai` | Is it running? Look for "active (running)". Press `q` to exit. |
| `journalctl -u densityai -f` | Watch its output live. Ctrl+C stops watching, not the service. |
| `sudo systemctl stop densityai` | Stop it now. It starts again at the next power-on. |
| `sudo systemctl start densityai` | Start it again. |
| `sudo systemctl restart densityai` | Restart it, e.g. after changing frontend code (it rebuilds the dashboard first, about a minute). |
| `sudo systemctl disable --now densityai` | Stop it and keep it from starting at power-on. |
| `sudo systemctl enable --now densityai` | Undo that: start it now and at every power-on. |

Settings such as `INGEST_TOKEN` go in `/etc/densityai.env`, one `NAME=value` per line, then restart the service. For a Wi-Fi camera instead of USB, add `CAMERA_URI=rtsp://...` there (see [Step 12 of the runbook](docs/jetson-setup.md#step-12-wi-fi-camera-tapo-c120)).

### Running by hand: `npm run serve`

Use this when you want the output in your terminal or the camera window, for example while aiming the camera or adjusting the counting region. **Stop the service first**: both use port 8000 and the camera, and `npm run serve` refuses to start ("Something is already running on port 8000") while the service is on.

```bash
sudo systemctl stop densityai
cd ~/DensityAi
npm run serve                  # in a terminal on the Jetson's own desktop
DISPLAY=:0 npm run serve       # over SSH (e.g. VS Code Remote): window appears on the Jetson's monitor
# ... Ctrl+C when done, then hand back to the service:
sudo systemctl start densityai
```

`npm run serve` runs [jetson/start.sh](jetson/start.sh), the same script the service uses. It:

- rebuilds the dashboard if the frontend, a `.env` file or `start.sh` changed since the last live build. The build never has a fixed backend address: `REACT_APP_API_URL` is ignored (with a warning if a `.env` file sets it), and the page talks to whatever address it was opened at.
- starts the backend on port 8000, reachable from other devices, and prints every address the dashboard can be opened at: `localhost`, each IP from `hostname -I` with its interface, `<hostname>.local`, and the Tailscale name and IP if Tailscale is connected
- waits for the USB camera, runs the pipeline, and restarts it whenever it stops. Unplugging and replugging the camera needs no command; the count shows Offline until the camera is back.
- stops everything cleanly on Ctrl+C

Over SSH without `DISPLAY=:0`, the pipeline runs without its window. Extra flags go to the pipeline, for example `npm run serve -- --tracker`.

### Reaching the Jetson on any network

The dashboard has no fixed address: it works at any address that reaches port 8000 on the Jetson, always over `http://` (the backend doesn't serve https). What changes from network to network is which address your laptop or phone can reach.

| Where | How | Open |
|---|---|---|
| Home Wi-Fi, your own router | Jetson and viewer on the same Wi-Fi | the Wi-Fi IP `npm run serve` prints, or `http://<hostname>.local:8000` |
| Phone hotspot | Jetson and viewers join the hotspot | the IP printed for the Wi-Fi interface |
| Campus, `eduroam` | Jetson and viewer both on eduroam (tested: a phone reached the dashboard) | the Wi-Fi IP `npm run serve` prints |
| Campus, `ncsu-guest` | Device-to-device traffic may be blocked | use eduroam, USB, a phone hotspot or Tailscale instead |
| USB cable | Jetson's USB-C port to the laptop (USB device mode) | `http://192.168.55.1:8000` |
| Tailscale | Jetson and viewers logged into the same tailnet; works on any network, campus included | the Tailscale name or IP printed |

- **USB** is the most reliable for a single laptop on demo day: no Wi-Fi involved. The Jetson's side of the link is always `192.168.55.1`, and the laptop gets an address automatically.
- **Tailscale** setup, once on the Jetson: `curl -fsSL https://tailscale.com/install.sh | sh && sudo tailscale up`, then install the Tailscale app on each laptop or phone and log in to the same account. Restart the service (or `npm run serve`) afterwards so it prints the Tailscale address.
- **`.local` names** need mDNS, which works from macOS, iOS and most Linux, but not always from Windows or Android. Use the IP there.
- If SSH to the Jetson works but the page doesn't, forward the port: `ssh -L 8000:localhost:8000 <user>@<jetson-address>`, then open `http://localhost:8000` on the laptop (VS Code Remote-SSH can do this from its Ports tab).
- The addresses are printed once at startup. If the Jetson joins a different network while running, check `hostname -I` again; no rebuild is needed.

**Stuck on "Connecting to the backend at …"?** If the address in that message isn't the one in your browser's address bar, the build has an old address baked in. Rebuild it:

```bash
rm -rf build && npm run serve                                   # by hand
rm -rf build && sudo systemctl restart densityai                # or with the service
```

### Separate terminals (development)

Stop the service first (`sudo systemctl stop densityai`), then run each command in its own terminal on the Jetson, in this order.

**1. Collector and web service** (PostgreSQL itself runs as a system service)

```bash
cd ~/DensityAi
npm run backend
```

**2. Frontend**, which opens at http://localhost:3000 in the Jetson's browser

```bash
cd ~/DensityAi
npm run start:live
```

**3. Video pipeline**

```bash
cd ~/DensityAi/jetson
python3 occupancy_pipeline.py
```

The pipeline reads the USB camera, counts people in the room region with PeopleNet and `nvdsanalytics`, and sends the counts to the backend. Only counts are sent, never frames. The exception is `--preview-dir`, which keeps the newest small annotated frame in RAM for the password-protected Admin page (`start.sh` turns it on when `ADMIN_PASSWORD` is set). It prints the count and FPS about once a second, and Ctrl+C stops it cleanly. It runs with the system `python3`, where `pyds` and `gi` are installed, not `backend/.venv`.

**Don't run `simulator.py` at the same time.** It and the pipeline both post as `cam-1`, so their counts would get mixed together on the dashboard.

**To view the dashboard from a laptop instead,** run step 2 on the laptop with:

```bash
REACT_APP_API_URL=http://<jetson-address>:8000 npm run start:live
```

`<jetson-address>` is any address from [Reaching the Jetson on any network](#reaching-the-jetson-on-any-network). This override only affects the dev server; don't put it in a `.env` file on the Jetson.

### Pipeline options

| Option | Default | What it does |
|---|---|---|
| `--camera-id` | `cam-1` | Camera name sent to the backend. It must be listed in `backend/zones.json`. |
| `--device` | `/dev/video0` | V4L2 camera device |
| `--infer-config` | `~/models/peoplenet/config_infer_peoplenet.txt` | PeopleNet `nvinfer` config |
| `--analytics-config` | `jetson/config_nvdsanalytics.txt` | ROI and line-crossing config |
| `--tracker` | off | Adds `nvtracker`. Needed for line crossing and dwell time. |
| `--no-display` | off | Uses `fakesink` instead of a window, for SSH or systemd runs |

The pipeline sends to the collector at `http://localhost:8001` by default. Set `DENSITY_COLLECTOR_URL` to change that, and `INGEST_TOKEN` if the collector has one set. With `--tracker` it also measures how long each person stays in the zone (dwell time) and sends that with the counts.

- **Demo 1 is ROI-only.** Line crossing is disabled (`enable=0`) in `config_nvdsanalytics.txt`, so entries and exits are sent as 0. Turn it on and run with `--tracker` for Demo 2.
- **Coordinates are scene-specific.** The ROI covers the whole frame for now. Re-derive it from a screenshot once the camera is mounted. `config-width` and `config-height` must stay equal to the 1280x720 stream resolution.

## Contributing

See [CLAUDE.md](CLAUDE.md) for project conventions. In short: functional components and hooks only, use the CSS variables in `App.css` for colors, ask before adding npm dependencies, and never commit secrets or `.env` files.
