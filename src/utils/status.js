// Single source of truth for occupancy status. Adjust thresholds as the team decides.
export const THRESHOLDS = { moderate: 50, busy: 75 };

export const OFFLINE = { key: 'offline', label: 'Offline', pct: 0 };

export function getStatus(count, capacity) {
  const pct = capacity > 0 ? (count / capacity) * 100 : 0;
  if (pct > THRESHOLDS.busy) return { key: 'busy', label: 'Busy', pct };
  if (pct >= THRESHOLDS.moderate) return { key: 'moderate', label: 'Moderate', pct };
  return { key: 'available', label: 'Available', pct };
}

// A zone whose cameras have stopped reporting has no trustworthy count.
export function getZoneStatus(zone) {
  return zone.stale ? OFFLINE : getStatus(zone.occupancy, zone.capacity);
}
