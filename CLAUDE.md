# CLAUDE.md

## Project overview
Web dashboard for our NC State senior design project: an AI camera-based, real-time room occupancy monitoring system. Cameras feed person detection (NVIDIA PeopleNet running on a Jetson Orin Nano), and this dashboard displays live counts plus historical trends across multiple rooms/zones.

**Primary goal of the UI:** answer "how busy is it RIGHT NOW?" at a glance. Trends and planning data are secondary and should never crowd out the live view.

## Milestones
- **Demo 1 (PoC), Oct 12–15:** single camera, one zone, live count.
- **Demo 2 (Design Day), Dec 1:** two zones, multiple cameras, full dashboard with history and trends.

Prioritize work that moves us toward these demos. Don't gold-plate features that neither demo needs.

## Tech stack
- React 18 (Create React App / `react-scripts` 5), plain JavaScript (no TypeScript)
- Recharts for charts, lucide-react for icons
- Plain CSS with CSS variables in `src/App.css` (no Tailwind, no CSS-in-JS)
- Backend: Python 3.9+, FastAPI + uvicorn, SQLite via stdlib `sqlite3` (no ORM). Deps in `backend/requirements.txt`, installed into `backend/.venv`

## Commands
- `npm install`: install dependencies
- `npm start`: dev server at http://localhost:3000
- `npm run build`: production build (run this to check for errors before finishing a task)
- `npm test`: run tests
- `npm run backend:setup`: create `backend/.venv` and install Python deps (once)
- `npm run backend`: FastAPI backend at http://localhost:8000 (auto-reloads)
- `npm run simulate`: fake Jetson that posts counts to the backend (`-- --help` for flags)
- `npm run start:live`: dev server using the backend instead of mock data
- `npm run backend:test`: backend tests (run these too before finishing backend work)

## Project structure
```
public/index.html              HTML entry
src/index.js                   React bootstrap
src/App.jsx                    Layout + sidebar nav; picks the page from the URL hash
src/pages/                     Dashboard, Zones, Trends, Settings pages
src/App.css                    All styles + CSS variables
src/hooks/useOccupancyData.js  Data-access layer: mock generators or live backend (REACT_APP_DATA_SOURCE)
src/hooks/useHashRoute.js      Tiny hash router (no react-router dependency)
src/services/api.js            Backend URL + WebSocket client (only used by useOccupancyData)
src/utils/fakeDataGenerator.js Mock data for all dashboard sections
src/utils/status.js            Shared status helper (thresholds live here only)
src/components/                KpiCards, SeatStrip, StatRow, OccupancyTrend, ZoneTable, TrafficChart, Insights
backend/app/main.py            FastAPI app: /api/ingest, /api/zones, /api/health, /ws/live
backend/app/processing.py      Pure logic: smoothing, multi-camera fusion, staleness, clock correction
backend/app/db.py              SQLite schema + writes
backend/zones.json             Zones (capacity, fusion) and which camera belongs to which zone
backend/simulator.py           Fake Jetson for development
jetson/occupancy_pipeline.py   DeepStream 7.1 app: USB camera -> PeopleNet -> nvdsanalytics ROI count -> probe_client
jetson/config_nvdsanalytics.txt ROI + line-crossing config (line crossing off for Demo 1)
jetson/setup_peoplenet.sh      Downloads PeopleNet and writes config_infer_peoplenet.txt (idempotent)
jetson/probe_client.py         Non-blocking sender the DeepStream probe calls on the Jetson
docs/jetson-setup.md           From-scratch Jetson runbook + known issues (source of truth for the Jetson)
```

## Data
- `npm start` uses mock data from `src/utils/fakeDataGenerator.js`. `npm run start:live` takes live zone counts from the backend over `/ws/live`; trends, traffic, stats and insights are still mock until the backend serves history (Phase 2).
- Treat the shapes returned by the generator functions as the **data contract**. The backend must return the same shapes (tests in `backend/tests/test_api.py` check the zone keys). When adding a feature, extend the generator and the backend together rather than hardcoding data in components.
- Keep data fetching isolated from rendering: only `useOccupancyData` talks to `src/services/api.js`; components just receive props.
- The backend sends counts and capacity, never a status. Busy/Available logic stays in `src/utils/status.js`.
- The Jetson sends aggregated counts only (never frames). The ingest payload and API are documented in the README's "Backend" section; the Jetson setup runbook is `docs/jetson-setup.md` (`occupancy-tracker-plan.md` has the background).

## Design guidelines
- Light theme, left sidebar nav, card-based layout. Visual references: "Occupancy Insight" style dashboards (KPI cards on top, trend chart + zone table, bidirectional in/out traffic chart, insights panel).
- Occupancy status colors: green = Available, blue = Moderate, red = Busy.
- Status thresholds (adjust as team decides): under 50% Available, 50–75% Moderate, over 75% Busy. Keep this logic in ONE shared helper, not duplicated per component.
- Use existing CSS variables in `App.css` for colors instead of new hardcoded hex values.

## Conventions
- Functional components and hooks only.
- Put new dashboard sections in their own file under `src/components/` rather than growing `App.jsx`.
- Ask before adding new npm dependencies.
- Keep the app runnable with `npm start` after every change.
- Every `nvvideoconvert` in DeepStream code needs `copy-hw=2` (DeepStream 7.1 on JetPack 6.2.x crashes after ~2 minutes without it).
- DeepStream config files (nvinfer, nvdsanalytics) use `#` comments only; `;` comments break parsing.
- `jetson/occupancy_pipeline.py` runs with the system `python3` (where `pyds` and `gi` are installed), not `backend/.venv`.
- Never commit secrets, API keys, or `.env` files. The ingest token comes from the `INGEST_TOKEN` env var.

## Working style
- Make small, focused changes and explain what changed and why.
- If a request is ambiguous or conflicts with this file, ask before proceeding.
