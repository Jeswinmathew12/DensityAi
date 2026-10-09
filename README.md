# DensityAI Dashboard

A web dashboard for real-time room occupancy monitoring, built for our NC State senior design project.

## Background

DensityAI is an AI camera-based occupancy monitoring system. Cameras feed a person-detection model (NVIDIA PeopleNet running on a Jetson Orin Nano), and this dashboard shows how busy each room or zone is, both live and over time.

The main goal of the UI is to answer **"how busy is it right now?"** at a glance. Trends and planning data are secondary and should never crowd out the live view.

### System overview

```
USB camera -> Jetson Orin Nano, JetPack 6.2.1 + DeepStream 7.1 (PeopleNet + tracker + line-crossing analytics)
           -> SQLite -> FastAPI REST/WebSocket -> React dashboard (this repo)
```

The Jetson pipeline is planned in [occupancy-tracker-plan.md](occupancy-tracker-plan.md). The backend in `backend/` receives counts, cleans them up, stores them and pushes live zone counts to the dashboard. Until the Jetson pipeline is running, `backend/simulator.py` stands in for it. The dashboard can also run on its own with mock data.

### Milestones

| Demo | Date | Scope |
|---|---|---|
| Demo 1 (proof of concept) | Oct 12-15 | Single camera, one zone, live count |
| Demo 2 (Design Day) | Dec 1 | Two zones, multiple cameras, full dashboard with history and trends |

### Features

- Four pages via the sidebar: Dashboard, Zones, Trends, Settings
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
src/pages/                     Dashboard, Zones, Trends, Settings pages
src/App.css                    All styles + CSS variables
src/hooks/useOccupancyData.js  Data-access layer: mock generators or live backend
src/hooks/useHashRoute.js      Tiny hash router (no react-router dependency)
src/services/api.js            Backend URL + WebSocket client
src/utils/fakeDataGenerator.js Mock data for all dashboard sections
src/utils/status.js            Shared status helper (thresholds live here only)
src/components/                KpiCards, SeatStrip, StatRow, OccupancyTrend, ZoneTable, TrafficChart, Insights
backend/                       FastAPI + SQLite backend, simulator, tests
docs/jetson-setup.md           Jetson setup runbook and known issues
jetson/setup_peoplenet.sh      Downloads PeopleNet and writes its nvinfer config
jetson/occupancy_pipeline.py   DeepStream pipeline: camera -> PeopleNet -> ROI count -> backend
jetson/config_nvdsanalytics.txt ROI and line-crossing config for the pipeline
jetson/probe_client.py         Sender the DeepStream probe calls on the Jetson
```

### Data

The shapes returned by `src/utils/fakeDataGenerator.js` are the data contract, and the backend returns the same shapes. `useOccupancyData.js` is the only file that knows whether data is mock or live.

## Backend

```
Jetson probe / simulator --POST /api/ingest (1 Hz per camera)--> FastAPI + SQLite --/ws/live--> dashboard
```

- **What the Jetson sends:** numbers only, never images. One JSON object per camera per second, or an array of them:
  ```json
  { "cameraId": "cam-1", "ts": 1759500000.0, "sentAt": 1759500000.2,
    "occupancy": 12, "entriesCum": 140, "exitsCum": 128, "fps": 27.4 }
  ```
  `occupancy` is the `nvdsanalytics` ROI count, and `entriesCum`/`exitsCum` are its cumulative line-crossing counts. `ts` is when the frame was counted and `sentAt` is when the request went out. The backend uses the gap to correct for the Jetson's clock being wrong. If `INGEST_TOKEN` is set, requests must send it as `X-Ingest-Token`.
- **Processing:**
  - The live count is the median of each camera's last 5 samples, which hides flicker and brief occlusions.
  - Cameras are combined per zone, using `"fusion": "sum"` (separate areas) or `"max"` (overlapping views) in `backend/zones.json`.
  - A zone is marked `stale` (shown as "Offline") when its cameras stop reporting for 10 seconds.
- **Endpoints:**
  - `GET /api/zones`: live zones, same shape as `generateZones()`
  - `GET /api/history`: last 24 local hours (trends, traffic) and today's stats and insights, built from stored samples. Same shapes as the mock generators, with `null` where there is no data, so a camera that was off shows as a gap, not 0.
  - `GET /api/health`: per-camera last-seen time and FPS
  - `WS /ws/live`: pushes `{ "type": "zones", "zones": [...] }` on connect and whenever counts change
  - `GET /`: the built dashboard, if a `build/` folder exists (see [Viewing on other devices](#viewing-on-other-devices))
- **Configuration:**
  - `backend/zones.json`: zones, capacities (usable seats), and which camera is in which zone
  - Env vars: `INGEST_TOKEN`, `DENSITY_DB` (default `backend/density.db`), `DENSITY_STATIC` (dashboard build folder, default `build/`), `DENSITY_TZ` (time zone for hourly history, default `America/New_York`)
  - Frontend: `REACT_APP_API_URL`. If unset, the dev server uses `http://localhost:8000` and a production build uses the address the page was loaded from.

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

Needs Python 3.9+. Use three terminals:

```bash
npm run backend:setup   # once: creates backend/.venv and installs FastAPI etc.
npm run backend:sim     # terminal 1: API at http://localhost:8000, history in backend/sim.db
npm run simulate        # terminal 2: fake Jetson posting counts every second
npm run start:live      # terminal 3: dashboard using the backend
```

With the real Jetson, use `npm run backend` instead of `backend:sim`. Real history lives in `backend/density.db` and simulated history in `backend/sim.db`, so the two never mix. The simulator refuses to post to a backend that is writing `density.db`.

To start history over (for example before a demo), stop the backend and run `npm run backend:reset`. It moves `backend/density.db` into `backend/backups/` rather than deleting it. Use `npm run backend:reset -- backend/sim.db` for the simulator's history.

Simulator options: `npm run simulate -- --hour 14` starts at 2 PM, `--speed 60` fast-forwards a minute per second, and `--dropout 0.02` makes cameras go silent now and then to test the offline state. On Windows, set `REACT_APP_DATA_SOURCE=live` in a `.env.local` file and use `npm start`, since the `start:live` script uses macOS/Linux syntax.

### Viewing on other devices

The backend can serve the dashboard itself, so anyone on the same network can open it in a browser with nothing to install. On the machine running the backend:

```bash
npm run build:live      # build the dashboard in live mode (repeat after frontend changes)
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8000
hostname -I             # this machine's IP address
```

Then on a phone or laptop, open `http://<that-ip>:8000`. The page connects to the backend at the same address automatically.

- `--host 0.0.0.0` is required. `npm run backend` only accepts connections from the same machine.
- Viewers must be on the same network. Campus Wi-Fi often blocks device-to-device traffic. If the page won't load, put everything on a phone hotspot or your own router.
- If the machine has a firewall, open port 8000 (for example `sudo ufw allow 8000`).

### Other commands

| Command | What it does |
|---|---|
| `npm start` | Dev server at http://localhost:3000 (mock data) |
| `npm run start:live` | Dev server using the backend |
| `npm run build` | Production build into `build/` (run this to check for errors) |
| `npm run build:live` | Production build using the backend, for serving from port 8000 |
| `npm test` | Run tests |
| `npm run backend` | Backend at http://localhost:8000, reloads on changes |
| `npm run backend:sim` | Backend using `backend/sim.db`, for the simulator |
| `npm run simulate` | Fake Jetson (`npm run simulate -- --help` for options) |
| `npm run backend:reset` | Move `backend/density.db` to `backend/backups/` so history starts empty |
| `npm run backend:test` | Backend tests |

## How to run on the Jetson

The Jetson already has everything installed. To rebuild one from scratch, follow [docs/jetson-setup.md](docs/jetson-setup.md).

Run each command in its own terminal on the Jetson, in this order.

**1. Backend**

```bash
cd ~/DensityAi
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8000
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

The pipeline reads the USB camera, counts people in the room region with PeopleNet and `nvdsanalytics`, and sends the counts to the backend. Only counts leave the Jetson, never frames. It prints the count and FPS about once a second, and Ctrl+C stops it cleanly. It runs with the system `python3`, where `pyds` and `gi` are installed, not `backend/.venv`.

**Don't run `simulator.py` at the same time.** It and the pipeline both post as `cam-1`, so their counts would get mixed together on the dashboard.

**To view the dashboard from a laptop instead,** run step 2 on the laptop with:

```bash
REACT_APP_API_URL=http://<jetson-ip>:8000 npm run start:live
```

### Pipeline options

| Option | Default | What it does |
|---|---|---|
| `--camera-id` | `cam-1` | Camera name sent to the backend. It must be listed in `backend/zones.json`. |
| `--device` | `/dev/video0` | V4L2 camera device |
| `--infer-config` | `~/models/peoplenet/config_infer_peoplenet.txt` | PeopleNet `nvinfer` config |
| `--analytics-config` | `jetson/config_nvdsanalytics.txt` | ROI and line-crossing config |
| `--tracker` | off | Adds `nvtracker`. Needed before enabling line crossing. |
| `--no-display` | off | Uses `fakesink` instead of a window, for SSH or systemd runs |

The pipeline sends to `http://localhost:8000` by default. Set `DENSITY_API_URL` to change that, and `INGEST_TOKEN` if the backend has one set.

- **Demo 1 is ROI-only.** Line crossing is disabled (`enable=0`) in `config_nvdsanalytics.txt`, so entries and exits are sent as 0. Turn it on and run with `--tracker` for Demo 2.
- **Coordinates are scene-specific.** The ROI covers the whole frame for now. Re-derive it from a screenshot once the camera is mounted. `config-width` and `config-height` must stay equal to the 1280x720 stream resolution.

## Contributing

See [CLAUDE.md](CLAUDE.md) for project conventions. In short: functional components and hooks only, use the CSS variables in `App.css` for colors, ask before adding npm dependencies, and never commit secrets or `.env` files.
