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

## Commands
- `npm install`: install dependencies
- `npm start`: dev server at http://localhost:3000
- `npm run build`: production build (run this to check for errors before finishing a task)
- `npm test`: run tests

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

## Data
- All data currently comes from `src/utils/fakeDataGenerator.js`. There is no backend yet.
- Treat the shapes returned by the generator functions as the **data contract**. When adding a feature, add or extend a generator function rather than hardcoding data in components.
- Later, generators will be swapped for real API/WebSocket calls from the Jetson pipeline, so keep data fetching isolated from rendering (e.g., a hook or service layer), not scattered through components.

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
- Never commit secrets, API keys, or `.env` files.

## Working style
- Make small, focused changes and explain what changed and why.
- If a request is ambiguous or conflicts with this file, ask before proceeding.
