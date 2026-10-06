# DensityAI Dashboard

A web dashboard for real-time room occupancy monitoring, built for our NC State senior design project.

## Background

DensityAI is an AI camera-based occupancy monitoring system. Cameras feed a person-detection model (NVIDIA PeopleNet running on a Jetson Orin Nano), and this dashboard shows how busy each room or zone is, both live and over time.

The main goal of the UI is to answer **"how busy is it right now?"** at a glance. Trends and planning data are secondary and should never crowd out the live view.

### System overview

```
USB camera -> Jetson Orin Nano (PeopleNet + tracker + line-crossing analytics)
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
  - `GET /api/health`: per-camera last-seen time and FPS
  - `WS /ws/live`: pushes `{ "type": "zones", "zones": [...] }` on connect and whenever counts change
- **Configuration:**
  - `backend/zones.json`: zones, capacities (usable seats), and which camera is in which zone
  - Env vars: `INGEST_TOKEN`, `DENSITY_DB` (default `backend/density.db`)
  - Frontend: `REACT_APP_API_URL` (default `http://localhost:8000`)

Coming for Demo 2: minute rollups and real history for Trends, traffic, stats and insights, served as part of the same contract.

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
npm run backend         # terminal 1: API at http://localhost:8000
npm run simulate        # terminal 2: fake Jetson posting counts every second
npm run start:live      # terminal 3: dashboard using the backend
```

Simulator options: `npm run simulate -- --hour 14` starts at 2 PM, `--speed 60` fast-forwards a minute per second, and `--dropout 0.02` makes cameras go silent now and then to test the offline state. On Windows, set `REACT_APP_DATA_SOURCE=live` in a `.env.local` file and use `npm start`, since the `start:live` script uses macOS/Linux syntax.

### Other commands

| Command | What it does |
|---|---|
| `npm start` | Dev server at http://localhost:3000 (mock data) |
| `npm run start:live` | Dev server using the backend |
| `npm run build` | Production build into `build/` (run this to check for errors) |
| `npm test` | Run tests |
| `npm run backend` | Backend at http://localhost:8000, reloads on changes |
| `npm run simulate` | Fake Jetson (`npm run simulate -- --help` for options) |
| `npm run backend:test` | Backend tests |

## Running on the Jetson

`jetson/occupancy_pipeline.py` reads the USB camera, counts people in the room region with PeopleNet and `nvdsanalytics`, and sends the counts to the backend through `jetson/probe_client.py`. Only counts leave the Jetson, never frames.

It needs JetPack 6.2, DeepStream 7.1 and pyds 1.2.0, and it runs with the **system `python3`** (where `pyds` and `gi` are installed), not `backend/.venv`. Setup steps are in [occupancy-tracker-plan.md](occupancy-tracker-plan.md).

```bash
# On the Jetson, from the repo root
export DENSITY_API_URL=http://localhost:8000   # where the backend runs (default shown)
export INGEST_TOKEN=...                        # only if the backend has one set
python3 jetson/occupancy_pipeline.py
```

The terminal prints the ROI count and FPS about once a second. Ctrl+C stops the pipeline cleanly. The first run builds a TensorRT engine, which can take several minutes and looks like a hang.

| Option | Default | What it does |
|---|---|---|
| `--camera-id` | `cam-1` | Camera name sent to the backend. It must be listed in `backend/zones.json`. |
| `--device` | `/dev/video0` | V4L2 camera device |
| `--infer-config` | `~/models/peoplenet/config_infer_peoplenet.txt` | PeopleNet `nvinfer` config |
| `--analytics-config` | `jetson/config_nvdsanalytics.txt` | ROI and line-crossing config |
| `--tracker` | off | Adds `nvtracker`. Needed before enabling line crossing. |
| `--no-display` | off | Uses `fakesink` instead of a window, for SSH or systemd runs |

- **Demo 1 is ROI-only.** Line crossing is disabled (`enable=0`) in `config_nvdsanalytics.txt`, so entries and exits are sent as 0. Turn it on and run with `--tracker` for Demo 2.
- **Coordinates are scene-specific.** The ROI covers the whole frame for now. Re-derive it from a screenshot once the camera is mounted. `config-width` and `config-height` must stay equal to the 1280x720 stream resolution.
- **Don't run the simulator at the same time.** Both would post as `cam-1`.
- **Every `nvvideoconvert` has `copy-hw=2`.** Without it, DeepStream 7.1 on JetPack 6.2 crashes after about two minutes with "Failed in mem copy".

## Contributing

See [CLAUDE.md](CLAUDE.md) for project conventions. In short: functional components and hooks only, use the CSS variables in `App.css` for colors, ask before adding npm dependencies, and never commit secrets or `.env` files.
