import { useEffect, useState } from 'react';
import {
  generateZones,
  generateOccupancyTrend,
  generateTraffic,
  generateDailyStats,
  generateInsights,
} from '../utils/fakeDataGenerator';

const load = () => ({
  zones: generateZones(),
  trend: generateOccupancyTrend(),
  traffic: generateTraffic(),
  stats: generateDailyStats(),
  insights: generateInsights(),
});

// Data-access layer: swap the internals for fetch/WebSocket when the Jetson API exists.
export default function useOccupancyData(intervalMs = 2000) {
  const [data, setData] = useState(load);

  useEffect(() => {
    const id = setInterval(() => setData(load()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs]);

  return data;
}
