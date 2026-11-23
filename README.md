# DensityAI Dashboard

A web dashboard for real-time room occupancy monitoring, built for our NC State senior design project.

## Background

DensityAI is an AI camera-based occupancy monitoring system. Cameras feed a person-detection model (NVIDIA PeopleNet running on a Jetson Orin Nano), and this dashboard shows how busy each room or zone is, both live and over time.

The main goal of the UI is to answer **"how busy is it right now?"** at a glance. Trends and planning data are secondary and should never crowd out the live view.

### System overview

```
USB or Wi-Fi (RTSP) camera -> Jetson Orin Nano, JetPack 6.2.1 + DeepStream 7.1 (PeopleNet + tracker + line-crossing analytics)
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
src/pages/                     Dashboard, Zones, Trends, Settings, Admin pages
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
jetson/start.sh                `npm run serve` and the boot service: backend + pipeline, auto-restart
jetson/network/                DensityAI Wi-Fi scripts: jetson-wifi.sh, set-camera.sh, fix-uplink.sh
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
  - `GET /api/history`: last 24 local hours of occupancy trends and aggregate/per-zone entry and exit counts, plus today's stats and structured demand/data insights. Insights use `{id, category, title, detail}`; the dashboard adds current capacity watches from live zone counts. Same shapes as the mock generators, with `null` where there is no data, so a camera that was off shows as a gap, not 0.
  - `GET /api/health`: per-camera last-seen time and FPS
  - `GET /api/admin/cameras`, `GET /api/admin/preview/{cameraId}`: the Admin page's camera list and newest annotated JPEG frame. Need `X-Admin-Password`; return 404 when `ADMIN_PASSWORD` is unset (admin off) or there's no frame from the last 5 s
  - `WS /ws/live`: pushes `{ "type": "zones", "zones": [...] }` on connect and whenever counts change
  - `GET /`: the built dashboard, if a `build/` folder exists (see [Viewing on other devices](#viewing-on-other-devices))
- **Configuration:**
  - `backend/zones.json`: zones, capacities (usable seats), and which camera is in which zone
  - Env vars: `INGEST_TOKEN`, `ADMIN_PASSWORD` (turns on the Admin page), `DENSITY_PREVIEW_DIR` (where the pipeline keeps preview frames, default `/dev/shm/densityai`), `DENSITY_DB` (default `backend/density.db`), `DENSITY_STATIC` (dashboard build folder, default `build/`), `DENSITY_TZ` (time zone for hourly history, default `America/New_York`)
  - Frontend: `REACT_APP_API_URL`, for the dev server only. If unset, the dev server uses `http://localhost:8000` and a production build uses the address the page was loaded from. `npm run serve` always builds with it unset (and warns if a `.env` file sets it), so the dashboard works on whatever network the Jetson is on.

In live mode the dashboard loads `/api/history` on connect and every minute, so nothing on screen is simulated. A new database starts empty, and history is kept across camera and backend restarts.

## How to run

### Prerequisites

- [Node.js](https://nodejs.org/) (LTS recommended) and npm. On macOS: `brew install node`

### Steps

```bash
git clone https://github.com/Jeswinmathew12/DensityAi.git
cd DensityAi
git checkout demo-day       # what the Jetson runs for Design Day, until it's merged into master
npm install
npm start
```

Open http://localhost:3000. Live counts drift with new mock data every 3 seconds. The default mock scenario is one Student Union with food-court seating and three restaurant queues, plus bookstore, card services, lounge, and entrance zones. It does not change the live camera configuration in `backend/zones.json`.

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
REACT_APP_API_URL= npm run build:live   # live-mode build with no fixed address (repeat after frontend changes)
backend/.venv/bin/uvicorn backend.app.main:create_app --factory --host 0.0.0.0 --port 8000
hostname -I                             # this machine's IP addresses
```

Then on a phone or laptop, open `http://<one-of-those-ips>:8000` (http, not https). The page connects to the backend at the same address automatically. On the Jetson, `npm run serve` does all of this and prints the addresses for you.

- `--host 0.0.0.0` is required. `npm run backend` only accepts connections from the same machine.
- Leave `REACT_APP_API_URL` empty for this build. If it's set (for example in `.env`), that address is baked into the build and the dashboard breaks on any other network.
- Viewers must be on the same network. On campus, `ncsu` and `ncsu-guest` block device-to-device traffic, so use the Jetson's own [DensityAI Wi-Fi](#demo-setup-the-densityai-wi-fi). See [Reaching the Jetson on any network](#reaching-the-jetson-on-any-network).
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
| `npm run serve` | Jetson: build if needed, backend on port 8000 for all devices, pipeline with auto-restart |
| `npm run backend:sim` | Backend using `backend/sim.db`, for the simulator |
| `npm run simulate` | Fake Jetson (`npm run simulate -- --help` for options) |
| `npm run backend:reset` | Move `backend/density.db` to `backend/backups/` so history starts empty |
| `npm run backend:test` | Backend tests |

## How to run on the Jetson

The Jetson already has everything installed. To rebuild one from scratch, follow [docs/jetson-setup.md](docs/jetson-setup.md).

### Demo setup: the DensityAI Wi-Fi

This is how we run it on campus and on demo day. The Jetson broadcasts its own Wi-Fi network called **DensityAI**. The Tapo camera, and anyone who wants to watch, join it. We do it this way because NC State Wi-Fi (`ncsu`, `ncsu-guest`, eduroam) blocks devices from talking to each other: the camera on campus Wi-Fi is invisible to the Jetson.

```
Tapo C120 camera --Wi-Fi--> DensityAI (the Jetson, 10.42.0.1) <--Wi-Fi-- phones and laptops
                                      |
                                   USB-C cable (optional) --> Mac on ncsu, with Internet Sharing
```

**Every time (nothing to type):**

1. Power on the Jetson and the camera. Wait about 2 minutes. The DensityAI Wi-Fi, the camera connection and the dashboard all start by themselves.
2. Open the dashboard. **Nothing opens by itself**; type the address:
   - **Any phone or laptop:** join the **DensityAI** Wi-Fi (ask the team for the password), then open **http://10.42.0.1:8000**. This works with no internet at all. That device has no internet while it's on DensityAI, unless a Mac is sharing it (next point).
   - **A Mac on the USB-C cable:** keep the Mac on `ncsu` (or home Wi-Fi), plug the Jetson's USB-C port into the Mac, and open **http://192.168.2.200:8000**. The Mac keeps its own internet. This needs Internet Sharing on, once: System Settings > General > Sharing > the (i) next to **Internet Sharing** > share your connection from **Wi-Fi** to **Linux for Tegra** > turn Internet Sharing on. macOS can't share eduroam, so the Mac must be on `ncsu` or home Wi-Fi. Without Internet Sharing, the cable address is http://192.168.55.1:8000 instead.
   - **On the Jetson itself:** http://localhost:8000.
3. Check the **Admin** page (if `ADMIN_PASSWORD` is set) to see what the camera sees.

The camera has a reserved address on DensityAI (ours is `10.42.0.108`), so nothing changes after a restart. The camera and counting don't need the Mac or any internet. The internet through the Mac is only for the Tapo app, which needs it to add or change the camera, and to give phones on DensityAI internet. Keep the camera within about 10 to 15 m of the Jetson, ideally in sight of it.

**If something's wrong:**

| Problem | Fix |
|---|---|
| Page won't load on DensityAI | Use `http://10.42.0.1:8000` exactly (http, not https). A tab opened on another network has the old address. |
| Page won't load on the Mac | Cable in? Internet Sharing on, with the Mac on `ncsu` (not eduroam)? Then `http://192.168.2.200:8000`. |
| Everything on DensityAI lost internet after the cable wiggled | From the Mac: `ssh -t <user>@192.168.2.200 "sudo ~/DensityAi/jetson/network/fix-uplink.sh"`. It runs every 10 s by itself too. |
| Zone says Offline | The camera is off, out of range, or on another network. In the Tapo app, check it's on DensityAI. Then `sudo jetson/network/set-camera.sh --find` on the Jetson shows its address. |
| Counts look doubled up close | Normal when someone fills the frame. Mount the camera high and a few meters back. |

**Setting it up on a new Jetson or camera:** follow [Step 13 of the runbook](docs/jetson-setup.md#step-13-densityai-wi-fi-for-campus-and-demo-day). The scripts are in `jetson/network/`: `jetson-wifi.sh` (creates the DensityAI Wi-Fi), `set-camera.sh` (points DensityAI at the camera) and `fix-uplink.sh` (internet through the Mac).

### Normal use: the boot service

The Jetson runs DensityAI as a background service called `densityai`. It starts by itself whenever the Jetson powers on, so on demo day you only need to:

1. Power on the Jetson and wait about 2 minutes.
2. Open the dashboard in a browser. **Nothing opens by itself**; type the address:
   - on the Jetson: `http://localhost:8000`
   - on the DensityAI Wi-Fi: `http://10.42.0.1:8000` ([Demo setup](#demo-setup-the-densityai-wi-fi))
   - on a laptop or phone on another network: one of the addresses the service prints at startup (`journalctl -u densityai | grep start`), or `http://<ip>:8000` with an IP from `hostname -I`. Which one works depends on the network; see [Reaching the Jetson on any network](#reaching-the-jetson-on-any-network).

The service runs the backend and the camera pipeline together, restarts the pipeline if the camera is unplugged or it crashes, and waits for the clock to sync after a power loss so counts aren't stamped 1970. It shows no camera window. Stopping it stops the dashboard too; history is kept in `backend/density.db`, and the time it was off shows as a gap.

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

Settings such as `INGEST_TOKEN` and `ADMIN_PASSWORD` go in `/etc/densityai.env`, one `NAME=value` per line, then restart the service. That file is outside git because it holds passwords. For a Wi-Fi camera instead of USB, `sudo jetson/network/set-camera.sh <camera-ip>` writes `CAMERA_URI=rtsp://...` there and restarts the service (`set-camera.sh usb` goes back to the USB camera). See [Step 12 of the runbook](docs/jetson-setup.md#step-12-wi-fi-camera-tapo-c120).

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
- waits for the camera (USB, or the Wi-Fi camera in `CAMERA_URI`), runs the pipeline, and restarts it whenever it stops. Unplugging and replugging the camera needs no command; the count shows Offline until the camera is back.
- stops everything cleanly on Ctrl+C

Over SSH without `DISPLAY=:0`, the pipeline runs without its window. Extra flags go to the pipeline, for example `npm run serve -- --tracker`.

### Reaching the Jetson on any network

The dashboard has no fixed address: it works at any address that reaches port 8000 on the Jetson, always over `http://` (the backend doesn't serve https). What changes from network to network is which address your laptop or phone can reach.

| Where | How | Open |
|---|---|---|
| **DensityAI Wi-Fi (campus, demo day)** | The Jetson's own network ([Demo setup](#demo-setup-the-densityai-wi-fi)); the camera and viewers join it | `http://10.42.0.1:8000` |
| USB cable + Mac Internet Sharing | Mac on `ncsu` shares Wi-Fi to "Linux for Tegra" ([Demo setup](#demo-setup-the-densityai-wi-fi)) | `http://192.168.2.200:8000` |
| USB cable, no sharing | Jetson's USB-C port to the laptop (USB device mode) | `http://192.168.55.1:8000` |
| Home Wi-Fi, your own router | Jetson and viewer on the same Wi-Fi (Jetson not running DensityAI) | the Wi-Fi IP `npm run serve` prints, or `http://<hostname>.local:8000` |
| Campus, `ncsu`, `ncsu-guest` | Device-to-device traffic is blocked (tested 2026-11-22: the Jetson couldn't reach the camera or the Mac) | use the DensityAI Wi-Fi |
| Campus, `eduroam` | A phone reached the dashboard once, but the Tapo camera can't join eduroam (it needs a username login), and a Mac can't share it | use the DensityAI Wi-Fi |
| Phone hotspot | Jetson and viewers join the hotspot. An iPhone can't pair a Tapo camera to its own hotspot | the IP printed for the Wi-Fi interface |
| Tailscale | Jetson and viewers logged into the same tailnet; works on any network, campus included | the Tailscale name or IP printed |

- **DensityAI** is what we use on campus: it needs no outside network, so nothing can block it. While it's on, the Jetson's Wi-Fi is busy being the network, so the Jetson's only internet is through the Mac's USB-C cable.
- **USB** is the most reliable for a single laptop: no Wi-Fi involved. Without Internet Sharing the Jetson's side of the link is always `192.168.55.1`, and the laptop gets an address automatically. With Internet Sharing on, use `192.168.2.200`.
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
| `--tracker` | off | Adds `nvtracker`. Needed before enabling line crossing. |
| `--no-display` | off | Uses `fakesink` instead of a window, for SSH or systemd runs |

The pipeline sends to `http://localhost:8000` by default. Set `DENSITY_API_URL` to change that, and `INGEST_TOKEN` if the backend has one set.

- **Demo 1 is ROI-only.** Line crossing is disabled (`enable=0`) in `config_nvdsanalytics.txt`, so entries and exits are sent as 0. Turn it on and run with `--tracker` for Demo 2.
- **Coordinates are scene-specific.** The ROI covers the whole frame for now. Re-derive it from a screenshot once the camera is mounted. `config-width` and `config-height` must stay equal to the 1280x720 stream resolution.

## Contributing

See [CLAUDE.md](CLAUDE.md) for project conventions. In short: functional components and hooks only, use the CSS variables in `App.css` for colors, ask before adding npm dependencies, and never commit secrets or `.env` files.
