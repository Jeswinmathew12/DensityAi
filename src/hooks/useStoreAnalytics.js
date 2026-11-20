import { useEffect, useState } from 'react';
import { DATA_SOURCE } from './useOccupancyData';
import { fetchAnalytics, fetchSites, fetchSystem } from '../services/api';
import { generateSites, generateStoreAnalytics, generateSystemStatus } from '../utils/fakeDataGenerator';

const REFRESH_MS = 60000;

// Polls `load` every `ms` while mounted. Keeps the last good answer if a refresh fails.
function usePolled(load, deps, ms = REFRESH_MS) {
  const [state, setState] = useState({ data: null, error: null });
  useEffect(() => {
    let cancelled = false;
    const run = () =>
      load()
        .then((data) => !cancelled && setState({ data, error: null }))
        .catch((error) => !cancelled && setState((s) => ({ data: s.data, error })));
    run();
    const id = setInterval(run, ms);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

// Sites the Store insights page can show: the live camera site and any sample stores.
export function useSites() {
  return usePolled(() => (DATA_SOURCE === 'live' ? fetchSites() : Promise.resolve(generateSites())), []);
}

// { data, error } with data in the shape of generateStoreAnalytics(), or null while loading.
export function useStoreAnalytics(siteId, days) {
  return usePolled(
    () => {
      if (!siteId) return new Promise(() => {});
      return DATA_SOURCE === 'live'
        ? fetchAnalytics(siteId, days)
        : Promise.resolve(generateStoreAnalytics(siteId, days));
    },
    [siteId, days]
  );
}

// Each hop from camera to dashboard and whether it is working, refreshed every few seconds.
export function useSystemStatus() {
  return usePolled(
    () => (DATA_SOURCE === 'live' ? fetchSystem() : Promise.resolve(generateSystemStatus())),
    [],
    5000
  );
}
