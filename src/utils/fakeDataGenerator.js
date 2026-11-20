// Mock data for the dashboard. The shapes returned here are the data contract;
// swap these for real API/WebSocket calls from the Jetson pipeline later.

const ZONES = [
  { id: 'zone-a', name: 'Zone A - Main Room', capacity: 40, cameras: 1 },
  { id: 'zone-b', name: 'Zone B - Lab', capacity: 25, cameras: 1 },
];

const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// Advance live counts by a small random step so they drift like a real feed.
// Same shape as generateZones(); pass the previous zones in.
export function stepZones(zones) {
  return zones.map((z) => ({
    ...z,
    occupancy: Math.max(0, Math.min(z.capacity, z.occupancy + rand(-2, 2))),
    lastUpdated: new Date().toISOString(),
  }));
}

// Smooth-ish daily curve: 0..1 peaking mid-afternoon.
const dayCurve = (hour) => Math.max(0, Math.sin(((hour - 7) / 12) * Math.PI));

export function generateZones() {
  return ZONES.map((z) => ({
    ...z,
    occupancy: rand(Math.round(z.capacity * 0.2), Math.round(z.capacity * 0.6)),
    lastUpdated: new Date().toISOString(),
    stale: false, // true when no camera in the zone has reported for 10s (backend only)
  }));
}

// { hour, label, occupancy }[] for the last 24 hours. The backend uses occupancy: null
// for hours with no camera data.
export function generateOccupancyTrend(zoneId = 'zone-a') {
  const zone = ZONES.find((z) => z.id === zoneId) || ZONES[0];
  const now = new Date().getHours();
  return Array.from({ length: 24 }, (_, i) => {
    const hour = (now - 23 + i + 24) % 24;
    return {
      hour,
      label: `${hour}:00`,
      occupancy: Math.round(zone.capacity * dayCurve(hour) * (0.8 + Math.random() * 0.2)),
    };
  });
}

// { hour, label, entries, exits }[] - exits are plotted negative by the chart.
// The backend uses null for hours with no camera data.
export function generateTraffic() {
  const now = new Date().getHours();
  return Array.from({ length: 24 }, (_, i) => {
    const hour = (now - 23 + i + 24) % 24;
    const base = dayCurve(hour) * 20;
    return {
      hour,
      label: `${hour}:00`,
      entries: Math.round(base * Math.random()),
      exits: Math.round(base * Math.random()),
    };
  });
}

// { peakHour, avgOccupancy, totalVisitors } - any of them null when there is no data yet
export function generateDailyStats() {
  return { peakHour: '2:00 PM', avgOccupancy: rand(8, 20), totalVisitors: rand(80, 220) };
}

export function generateInsights() {
  return [
    { id: 1, text: 'Zone A is typically busiest between 1-3 PM.' },
    { id: 2, text: 'Zone B is quietest before 10 AM.' },
  ];
}

// ---- Store insights (sample retail store) -------------------------------------------------
// Same shapes as the web service's /api/sites and /api/sites/{id}/analytics. The backend's
// backend/mock_store.py generates the same kind of store as real events in PostgreSQL.

const STORE_ZONES = [
  { id: 'entrance', name: 'Entrance', capacity: 20, role: 'entrance' },
  { id: 'produce', name: 'Fresh produce', capacity: 30, role: null },
  { id: 'snacks', name: 'Snacks and drinks', capacity: 20, role: null },
  { id: 'endcap', name: 'Seasonal end-cap', capacity: 8, role: 'promo' },
  { id: 'pharmacy', name: 'Pharmacy counter', capacity: 12, role: null },
  { id: 'checkout', name: 'Checkout lanes', capacity: 20, role: 'checkout', alertAt: 16 },
];
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const WEEKDAY_FACTOR = [0.82, 0.78, 0.9, 0.97, 1.15, 1.38, 1.12];
const hourLabel = (h) => `${h % 12 || 12} ${h < 12 ? 'AM' : 'PM'}`;

// Seeded random numbers, so the sample store doesn't change on every refresh.
function seeded(seed) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const bump = (h, c, w, height) => height * Math.exp(-(((h - c) / w) ** 2));
const shoppersCurve = (h, weekend) =>
  weekend
    ? 0.15 + bump(h, 13, 2.6, 1.15) + bump(h, 17.5, 1.5, 0.3)
    : 0.22 + bump(h, 8.2, 0.9, 0.22) + bump(h, 12.4, 1, 0.6) + bump(h, 17.6, 1.4, 0.8);

// [{ id, name, kind, tz, live, zones, cameras }]
export function generateSites() {
  return [
    { id: 'sample-store', name: 'Maple Street Market (sample data)', kind: 'sample', tz: 'America/New_York',
      live: false, zones: STORE_ZONES, cameras: [] },
    { id: 'live', name: 'Live camera (demo table)', kind: 'live', tz: 'America/New_York', live: true,
      zones: ZONES.map(({ cameras, ...z }) => z), cameras: [{ id: 'cam-1', zoneId: 'zone-a' }] },
  ];
}

// { site, range, kpis, daily, byWeekday, byHour, heatmap, zones, zoneShare, dwellBuckets,
//   alerts, recommendations }. Numbers are null where there is no data.
export function generateStoreAnalytics(siteId = 'sample-store', days = 28) {
  const rnd = seeded(7 + days);
  const site = generateSites().find((s) => s.id === siteId) || generateSites()[0];
  const today = new Date();
  const daily = Array.from({ length: days }, (_, i) => {
    const d = new Date(today);
    d.setDate(today.getDate() - (days - 1 - i));
    const wd = (d.getDay() + 6) % 7;
    const full = Math.round(1100 * WEEKDAY_FACTOR[wd] * (0.9 + rnd() * 0.2));
    return {
      date: d.toISOString().slice(0, 10),
      label: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      weekday: DAYS[wd],
      visitors: i === days - 1 ? Math.round(full * 0.55) : full,
    };
  });
  const complete = daily.slice(0, -1);
  const byWeekday = DAYS.map((day) => {
    const v = complete.filter((d) => d.weekday === day).map((d) => d.visitors);
    return { day, visitors: v.length ? Math.round(v.reduce((a, b) => a + b, 0) / v.length) : null };
  });
  const hours = Array.from({ length: 15 }, (_, i) => i + 7);
  const weekdaySum = hours.reduce((s, h) => s + shoppersCurve(h + 0.5, false), 0);
  const byHour = hours.map((h) => ({
    hour: h, label: hourLabel(h), visitors: Math.round((1080 * shoppersCurve(h + 0.5, false)) / weekdaySum * 10) / 10,
  }));
  const heatmap = DAYS.map((day, d) => {
    const weekend = d >= 5;
    const sum = hours.reduce((s, h) => s + shoppersCurve(h + 0.5, weekend), 0);
    return {
      day,
      cells: hours.map((h) => ({
        hour: h, label: hourLabel(h),
        value: Math.round(((1100 * WEEKDAY_FACTOR[d] * shoppersCurve(h + 0.5, weekend)) / sum) * 2.1 * (0.92 + rnd() * 0.16) * 10) / 10,
      })),
    };
  });
  const visitors = complete.reduce((s, d) => s + d.visitors, 0) + daily[days - 1].visitors;
  const reach = { entrance: 100, produce: 57, snacks: 50, endcap: 70, pharmacy: 19, checkout: 86 };
  const dwellAvg = { produce: 168, snacks: 79, endcap: 30, pharmacy: 300, checkout: 160 };
  const engaged = { produce: 100, snacks: 96, endcap: 37, pharmacy: 100, checkout: 100 };
  const peak = { entrance: 1, produce: 6, snacks: 3, endcap: 2, pharmacy: 7, checkout: 19 };
  const alertCount = Math.round(days * 0.8);
  const zones = STORE_ZONES.map((z) => ({
    id: z.id, name: z.name, role: z.role, capacity: z.capacity,
    visits: Math.round((visitors * reach[z.id]) / 100), reachPct: reach[z.id],
    avgDwellSec: dwellAvg[z.id] ?? null, medianDwellSec: dwellAvg[z.id] ? Math.round(dwellAvg[z.id] * 0.85) : null,
    engagedPct: engaged[z.id] ?? null, avgOccupancy: Math.round(peak[z.id] * 3.3) / 10,
    peakOccupancy: peak[z.id], peakUtilPct: Math.round((100 * peak[z.id]) / z.capacity),
    alerts: z.id === 'checkout' ? alertCount : 0,
  }));
  const shoppable = zones.filter((z) => z.role !== 'entrance');
  const shareTotal = shoppable.reduce((s, z) => s + z.visits, 0);
  const zoneShare = shoppable.map((z) => ({
    zoneId: z.id, name: z.name, visits: z.visits, sharePct: Math.round((100 * z.visits) / shareTotal),
  }));
  const alerts = Array.from({ length: Math.min(alertCount, 6) }, (_, i) => {
    const t = new Date(today);
    t.setDate(today.getDate() - i * 2);
    t.setHours(i % 2 ? 13 : 17, 10 + i * 7, 30, 0);
    const n = 16 + (i % 3);
    return {
      time: t.toISOString(), zoneId: 'checkout', zone: 'Checkout lanes', people: n,
      text: `Checkout lanes reached ${n} people (${Math.round((100 * n) / 20)}% of capacity). Open another lane.`,
    };
  });
  const result = {
    site: { id: site.id, name: site.name, kind: site.kind },
    range: { from: daily[0].date, to: daily[days - 1].date, days, daysWithData: days },
    kpis: {
      visitors, visitorsPerDay: Math.round(complete.reduce((s, d) => s + d.visitors, 0) / complete.length),
      visitorsChangePct: 3, avgDwellSec: 118, conversionPct: 86, busiest: 'Sat 1 PM', alerts: alertCount,
    },
    daily, byWeekday, byHour, heatmap, zones, zoneShare,
    dwellBuckets: [
      { label: 'Under 30 s', count: Math.round(visitors * 0.47) },
      { label: '30 s to 2 min', count: Math.round(visitors * 1.1) },
      { label: '2 to 5 min', count: Math.round(visitors * 0.88) },
      { label: 'Over 5 min', count: Math.round(visitors * 0.36) },
    ],
    alerts,
    recommendations: [
      { id: 1, kind: 'staffing', title: 'Staff up for Sat 1 PM',
        text: `Saturdays at 1 PM are the busiest hour, with 34 shoppers in the store on average. Checkout reached its crowding alert ${alertCount} times in this period, so schedule an extra cashier for that window.` },
      { id: 2, kind: 'operations', title: 'Restock on Tue 9 PM',
        text: "Tuesday at 9 PM is the quietest open hour (2 shoppers on average). Use it for restocking, cleaning and planogram changes so they don't get in shoppers' way." },
      { id: 3, kind: 'marketing', title: 'Fill the slow Tuesday',
        text: 'Saturday brings 1.7x the shoppers of Tuesday. A Tuesday-only promotion could move some of that demand to the slow day.' },
      { id: 4, kind: 'layout', title: 'Make Seasonal end-cap work harder',
        text: '70% of shoppers walk past Seasonal end-cap, but only 37% of them stop for 30 seconds or more. Try a new display or price callout for two weeks and compare this number before and after.' },
      { id: 5, kind: 'layout', title: 'Bring more shoppers to Pharmacy counter',
        text: 'Only 19% of visitors reach Pharmacy counter. Signage near the entrance or moving a popular item next to it would raise that.' },
    ],
  };
  return result;
}

// { site, cameras, collector, database, web }: each hop from camera to dashboard.
export function generateSystemStatus() {
  const now = Date.now() / 1000;
  return {
    site: { id: 'live', name: 'Live camera (demo table)', kind: 'live', tz: 'America/New_York' },
    cameras: [{ id: 'cam-1', zoneId: 'zone-a', lastSeen: new Date().toISOString(), fps: 29.6, stale: false }],
    collector: { eventsLastMinute: 64, lastEventAt: now },
    database: { name: 'densityai', timescale: false, events: 412880 },
    web: { lastPoll: now, dashboards: 1 },
  };
}
