import {
  generateDailyStats,
  generateInsights,
  generateOccupancyTrend,
  generateTraffic,
  generateTrafficByZone,
  generateZones,
} from './fakeDataGenerator';

test('generates the selected Student Union zones with counts within capacity', () => {
  const zones = generateZones();

  expect(zones.map((zone) => zone.id)).toEqual([
    'food-court-seating',
    'grill-queue',
    'pizza-pasta-queue',
    'coffee-smoothies-queue',
    'bookstore-floor',
    'card-services',
    'student-lounge',
    'main-entrance-lobby',
  ]);
  expect(zones.every((zone) => zone.occupancy >= 0 && zone.occupancy <= zone.capacity)).toBe(true);
});

test('generates a capacity-bounded 24-hour trend for every demo zone', () => {
  const zones = generateZones();

  zones.forEach((zone) => {
    const trend = generateOccupancyTrend(zone.id);
    expect(trend).toHaveLength(24);
    expect(trend.every((point) => point.occupancy >= 0 && point.occupancy <= zone.capacity)).toBe(true);
  });
});

test('zone traffic sums to the all-zone traffic series', () => {
  const zones = generateZones();
  const zoneIds = zones.map((zone) => zone.id);
  const trafficByZone = generateTrafficByZone(zoneIds);
  const traffic = generateTraffic(trafficByZone);

  expect(Object.keys(trafficByZone)).toEqual(zoneIds);
  expect(traffic).toHaveLength(24);
  traffic.forEach((point, index) => {
    expect(point.entries).toBe(
      zones.reduce((sum, zone) => sum + trafficByZone[zone.id][index].entries, 0)
    );
    expect(point.exits).toBe(
      zones.reduce((sum, zone) => sum + trafficByZone[zone.id][index].exits, 0)
    );
  });
});

test('generates ranked demand insights from observed zone peaks only', () => {
  const zones = [
    { id: 'zone-a', name: 'Zone A', capacity: 10 },
    { id: 'zone-b', name: 'Zone B', capacity: 20 },
    { id: 'zone-c', name: 'Zone C', capacity: 5 },
  ];
  const trends = {
    'zone-a': [
      { hour: 9, occupancy: 4 },
      { hour: 14, occupancy: 8 },
      { hour: 18, occupancy: 10 },
    ],
    'zone-b': [{ hour: 13, occupancy: 15 }],
    'zone-c': [
      { hour: 10, occupancy: 0 },
      { hour: 11, occupancy: null },
    ],
  };

  expect(generateInsights(zones, trends, 15)).toEqual([
    {
      id: 'demand-zone-a',
      category: 'demand',
      title: 'Zone A peak demand',
      detail: '8 people at 2:00 PM today; 80% of capacity.',
    },
    {
      id: 'demand-zone-b',
      category: 'demand',
      title: 'Zone B peak demand',
      detail: '15 people at 1:00 PM today; 75% of capacity.',
    },
  ]);
});

test('every demo zone has nonzero crossings during its daily activity peak', () => {
  const zones = generateZones();
  const trafficByZone = generateTrafficByZone(zones.map((zone) => zone.id));

  zones.forEach((zone) => {
    expect(trafficByZone[zone.id].some((point) => point.entries > 0 && point.exits > 0)).toBe(true);
  });
});

test('daily stats use today’s trend points and traffic entries', () => {
  const zones = generateZones();
  const trends = Object.fromEntries(zones.map((zone) => [
    zone.id,
    Array.from({ length: 24 }, (_, hour) => ({ hour, occupancy: hour + 1 })),
  ]));
  const traffic = Array.from({ length: 24 }, (_, hour) => ({ hour, entries: hour + 1 }));
  const currentHour = new Date().getHours();
  const todayHours = Array.from({ length: currentHour + 1 }, (_, hour) => hour).filter((hour) => hour >= 7);
  const measuredHours = todayHours.length ? todayHours : [currentHour];
  const expectedAverage = Math.round(
    measuredHours.reduce((sum, hour) => sum + zones.length * (hour + 1), 0) / measuredHours.length
  );
  const expectedEntries = traffic
    .filter((point) => point.hour <= currentHour)
    .reduce((sum, point) => sum + point.entries, 0);

  expect(generateDailyStats(trends, traffic)).toMatchObject({
    avgOccupancy: expectedAverage,
    totalVisitors: expectedEntries,
  });
});
