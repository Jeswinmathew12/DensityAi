# Design Day talking points (Dec 1, 2026)

A short script for the booth. Bring the camera and the Jetson, have the dashboard open on a laptop, and be excited: this is a working product, not a slide.

## 1. Who we are (30 seconds)

- Each team member: name, major, and the part of DensityAI they built (Jetson and vision pipeline, backend and database, dashboard, business plan).

## 2. The problem (30 seconds)

- Stores make big decisions (how many cashiers to schedule, where to put a promotion, when to restock) mostly on gut feel. Online stores know exactly what shoppers look at; physical stores don't.
- People-counting tools today are either a door clicker (only "how many came in") or expensive enterprise systems.

## 3. What DensityAI does (1 minute, show the live camera)

- An AI camera counts people in each zone of a store in real time: how many are there now, how many walked in, how long they stay.
- Point at the camera, walk into the zone, and show the **Dashboard** count change.
- Privacy by design: the video is processed on the device and thrown away. Only numbers leave the camera.

## 4. How it is built (1 minute, show the System page)

Camera and NVIDIA Jetson (PeopleNet person detection) -> collector -> PostgreSQL events database -> web service (REST API) -> dashboard.

- The edge device only counts. A separate collector writes every count, entry, exit, visit length and alert into one events table.
- A real web service reads the database. The dashboard never talks to the camera, so in a deployment the Jetson stays in the store and the server can be anywhere, including the cloud. Open `/docs` on the web service to show the live API.
- One collector can take counts from many cameras and many stores.

## 5. What a store learns (2 minutes, show Store insights with the sample store)

The sample store is generated data (real campus data wasn't possible this semester), but it goes through the same database and API as the live camera. Walk through it as a store manager would:

- **Busiest times heatmap:** Saturday midday and weekday 5 to 6 PM are the peaks. Decision: schedule cashiers to match.
- **Crowding alerts:** checkout hit its alert level many times, always at those peaks. Decision: open another lane at that time, before the line forms.
- **Visitors by weekday:** Saturday brings about 1.7x Tuesday. Decision: a Tuesday-only promotion to fill the slow day.
- **Where shoppers go (pie) and the zone scorecard:** only about 1 in 5 shoppers reaches the pharmacy. Decision: signage at the entrance.
- **How long shoppers stay (pie):** 70% of shoppers pass the seasonal end-cap, but only about a third stop for 30 seconds. Decision: test a new display and measure the change, like an A/B test for the physical store.
- **Recommended actions:** the dashboard turns the numbers into plain-language actions.

## 6. Business plan (1 minute)

- **Customers:** grocery and drug stores, convenience chains, then libraries, gyms and campus buildings (the same product answers "how busy is it right now?").
- **Model:** hardware at cost plus a monthly subscription per camera for the dashboard, alerts and reports. Edge processing keeps cloud costs low.
- **Why us:** low-cost edge hardware, privacy-first (no video leaves the store), insights a manager can act on rather than raw counts.
- **Market timing:** retailers are adding in-store ad screens and need proof that shoppers stop and look; dwell time in a zone is exactly that proof.

## 7. What's next (30 seconds)

- More cameras per store and zone-to-zone flow (which aisle shoppers visit after which).
- A heatmap of where people stand, computed on the device.
- Live alerts to staff phones (for example "checkout queue over 8, open a lane").
- Forecasting: predict tomorrow's busy hours from history and weather.
- A pilot with a real store.

## Before the demo

- `npm run mock-store` the morning of the demo, so the sample store ends "today".
- `npm run backend:reset` if the live camera's history has old test data.
- Check the System page: every step should say Working.
