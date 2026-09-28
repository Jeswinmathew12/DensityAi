// Mock data for the dashboard. The shapes returned here are the data contract;
// swap these for real API/WebSocket calls from the Jetson pipeline later.

const ZONES = [
  { id: 'zone-a', name: 'Zone A - Main Room', capacity: 40, cameras: 1 },
  { id: 'zone-b', name: 'Zone B - Lab', capacity: 25, cameras: 1 },
];

const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// Smooth-ish daily curve: 0..1 peaking mid-afternoon.
const dayCurve = (hour) => Math.max(0, Math.sin(((hour - 7) / 12) * Math.PI));

export function generateZones() {
  return ZONES.map((z) => ({
    ...z,
    occupancy: Math.min(z.capacity, rand(0, z.capacity)),
    lastUpdated: new Date().toISOString(),
  }));
}

// { zoneId, hour, label, occupancy }[] for the last 24 hours
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

// { hour, label, entries, exits }[] - exits are plotted negative by the chart
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

// { peakHour, avgOccupancy, totalVisitors }
export function generateDailyStats() {
  return { peakHour: '2:00 PM', avgOccupancy: rand(8, 20), totalVisitors: rand(80, 220) };
}

export function generateInsights() {
  return [
    { id: 1, text: 'Zone A is typically busiest between 1-3 PM.' },
    { id: 2, text: 'Zone B is quietest before 10 AM.' },
  ];
}
