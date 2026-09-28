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

The Jetson pipeline and API are planned in [occupancy-tracker-plan.md](occupancy-tracker-plan.md). **There is no backend yet.** The dashboard currently runs on mock data.

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
src/hooks/useOccupancyData.js  Data-access layer (currently steps the fake generators)
src/hooks/useHashRoute.js      Tiny hash router (no react-router dependency)
src/utils/fakeDataGenerator.js Mock data for all dashboard sections
src/utils/status.js            Shared status helper (thresholds live here only)
src/components/                KpiCards, OccupancyTrend, ZoneTable, TrafficChart, Insights
```

### Data

All data comes from `src/utils/fakeDataGenerator.js`. The shapes it returns are the data contract. When the Jetson API exists, only `useOccupancyData.js` should need to change (swap the generators for `fetch` or WebSocket calls).

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

### Other commands

| Command | What it does |
|---|---|
| `npm start` | Dev server at http://localhost:3000 |
| `npm run build` | Production build into `build/` (run this to check for errors) |
| `npm test` | Run tests |

## Contributing

See [CLAUDE.md](CLAUDE.md) for project conventions. In short: functional components and hooks only, use the CSS variables in `App.css` for colors, ask before adding npm dependencies, and never commit secrets or `.env` files.
