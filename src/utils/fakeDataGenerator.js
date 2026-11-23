// Mock data for the dashboard. The shapes returned here are the data contract;
// swap these for real API/WebSocket calls from the Jetson pipeline later.

const peak = (hour, center, spread) => {
  const difference = Math.abs(hour - center);
  const distance = Math.min(difference, 24 - difference);
  return Math.exp(-0.5 * ((distance / spread) ** 2));
};

const activityProfile = (base, peaks) => (hour) =>
  Math.min(0.95, base + peaks.reduce((total, [center, strength, spread]) =>
    total + strength * peak(hour, center, spread), 0));

const ZONES = [
  {
    id: 'food-court-seating',
    name: 'Food Court Seating',
    capacity: 120,
    cameras: 1,
    activity: activityProfile(0.025, [[12.5, 0.58, 1.4], [18, 0.3, 1.5]]),
  },
  {
    id: 'grill-queue',
    name: 'Grill Queue',
    capacity: 18,
    cameras: 1,
    activity: activityProfile(0.01, [[12, 0.7, 0.7], [18, 0.25, 0.8]]),
  },
  {
    id: 'pizza-pasta-queue',
    name: 'Pizza/Pasta Queue',
    capacity: 16,
    cameras: 1,
    activity: activityProfile(0.01, [[12.5, 0.58, 0.8], [18, 0.32, 0.9]]),
  },
  {
    id: 'coffee-smoothies-queue',
    name: 'Coffee/Smoothies Queue',
    capacity: 14,
    cameras: 1,
    activity: activityProfile(0.01, [[8.5, 0.58, 0.8], [14.5, 0.32, 0.9]]),
  },
  {
    id: 'bookstore-floor',
    name: 'Bookstore Floor',
    capacity: 70,
    cameras: 1,
    activity: activityProfile(0.025, [[11, 0.34, 1.8], [15, 0.26, 1.8]]),
  },
  {
    id: 'card-services',
    name: 'Student ID/Card Services',
    capacity: 24,
    cameras: 1,
    activity: activityProfile(0.01, [[9.5, 0.68, 0.9], [13.5, 0.28, 1]]),
  },
  {
    id: 'student-lounge',
    name: 'Student Lounge/Event Commons',
    capacity: 55,
    cameras: 1,
    activity: activityProfile(0.025, [[12.5, 0.2, 1.4], [17.5, 0.55, 1.7]]),
  },
  {
    id: 'main-entrance-lobby',
    name: 'Main Entrance Lobby',
    capacity: 40,
    cameras: 1,
    activity: activityProfile(0.025, [
      [8, 0.35, 0.35],
      [10, 0.25, 0.35],
      [12, 0.38, 0.4],
      [14, 0.25, 0.35],
      [16, 0.35, 0.4],
      [18, 0.18, 0.5],
    ]),
  },
];

const rand = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

const simulatedCount = (zone, hour) =>
  Math.min(zone.capacity, Math.round(zone.capacity * zone.activity(hour) * (0.85 + Math.random() * 0.3)));

const hourLabel = (hour) => `${hour % 12 || 12}:00 ${hour < 12 ? 'AM' : 'PM'}`;

// Advance live counts by a small random step so they drift like a real feed.
// Same shape as generateZones(); pass the previous zones in.
export function stepZones(zones) {
  return zones.map((z) => ({
    ...z,
    occupancy: Math.max(0, Math.min(z.capacity, z.occupancy + rand(-2, 2))),
    lastUpdated: new Date().toISOString(),
  }));
}

export function generateZones() {
  const hour = new Date().getHours();
  return ZONES.map((z) => ({
    id: z.id,
    name: z.name,
    capacity: z.capacity,
    cameras: z.cameras,
    occupancy: simulatedCount(z, hour),
    lastUpdated: new Date().toISOString(),
    stale: false,
  }));
}

// { hour, label, occupancy }[] for the last 24 hours. The backend uses occupancy: null
// for hours with no camera data.
export function generateOccupancyTrend(zoneId = 'food-court-seating') {
  const zone = ZONES.find((z) => z.id === zoneId) || ZONES[0];
  const now = new Date().getHours();
  return Array.from({ length: 24 }, (_, i) => {
    const hour = (now - 23 + i + 24) % 24;
    return {
      hour,
      label: `${hour}:00`,
      occupancy: simulatedCount(zone, hour),
    };
  });
}

// { zoneId: { hour, label, entries, exits }[] } - the backend uses null when there is no data.
export function generateTrafficByZone(zoneIds = ZONES.map((zone) => zone.id)) {
  const now = new Date().getHours();
  return Object.fromEntries(zoneIds.map((zoneId) => {
    const zone = ZONES.find((item) => item.id === zoneId);
    if (!zone) return [zoneId, []];
    return [zoneId, Array.from({ length: 24 }, (_, i) => {
      const hour = (now - 23 + i + 24) % 24;
      const flow = zone.capacity * zone.activity(hour) * 0.45;
      return {
        hour,
        label: `${hour}:00`,
        entries: Math.round(flow * (0.7 + Math.random() * 0.6)),
        exits: Math.round(flow * (0.7 + Math.random() * 0.6)),
      };
    })];
  }));
}

// Building-wide series for the Trends page, summed from zone crossing counts.
export function generateTraffic(trafficByZone) {
  const series = Object.values(trafficByZone);
  if (!series.length || !series[0].length) return [];
  return series[0].map((point, index) => ({
    hour: point.hour,
    label: point.label,
    entries: series.reduce((total, zone) => total + (zone[index]?.entries ?? 0), 0),
    exits: series.reduce((total, zone) => total + (zone[index]?.exits ?? 0), 0),
  }));
}

// { peakHour, avgOccupancy, totalVisitors } - any of them null when there is no data yet
export function generateDailyStats(trends, traffic) {
  const currentHour = new Date().getHours();
  const todayHours = Array.from({ length: currentHour + 1 }, (_, hour) => hour)
    .filter((hour) => hour >= 7);
  const measuredHours = todayHours.length ? todayHours : [currentHour];
  const hourlyTotals = measuredHours.map((hour) =>
    ZONES.reduce((total, zone) => {
      const point = trends[zone.id].find((item) => item.hour === hour);
      return total + (point?.occupancy ?? 0);
    }, 0));
  const peakIndex = hourlyTotals.indexOf(Math.max(...hourlyTotals));
  const entriesToday = traffic
    .filter((item) => item.hour <= currentHour)
    .reduce((total, item) => total + item.entries, 0);

  return {
    peakHour: hourLabel(measuredHours[peakIndex]),
    avgOccupancy: Math.round(hourlyTotals.reduce((total, value) => total + value, 0) / hourlyTotals.length),
    totalVisitors: entriesToday,
  };
}

export function generateInsights(zones = [], trends = {}, currentHour = new Date().getHours()) {
  return zones
    .map((zone) => {
      const points = (trends[zone.id] || []).filter(
        (point) => point.hour <= currentHour && point.occupancy != null
      );
      if (!points.length) return null;

      const peak = points.reduce((highest, point) =>
        point.occupancy > highest.occupancy ? point : highest
      );
      if (peak.occupancy <= 0) return null;
      const percent = zone.capacity > 0
        ? Math.round((peak.occupancy / zone.capacity) * 100)
        : null;

      return {
        id: `demand-${zone.id}`,
        category: 'demand',
        title: `${zone.name} peak demand`,
        detail: `${peak.occupancy} ${peak.occupancy === 1 ? 'person' : 'people'} at ${hourLabel(peak.hour)} today${percent == null ? '.' : `; ${percent}% of capacity.`}`,
        score: percent ?? peak.occupancy,
      };
    })
    .filter(Boolean)
    .sort((a, b) => b.score - a.score)
    .map(({ score, ...insight }) => insight);
}
