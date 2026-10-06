import React from 'react';
import { OFFLINE, getStatus } from '../utils/status';
import SeatStrip from './SeatStrip';
import StatRow from './StatRow';

// What the "Live now" line should say, given the backend connection and camera health.
function liveLabel(connection, offlineZones, totalZones) {
  if (connection !== 'open') return { text: 'Reconnecting to live feed…', ok: false };
  if (offlineZones === totalZones) return { text: 'No camera data', ok: false };
  if (offlineZones > 0) return { text: `Live now · ${offlineZones} zone${offlineZones === 1 ? '' : 's'} offline`, ok: false };
  return { text: 'Live now', ok: true };
}

export default function KpiCards({ zones, stats, connection = 'open' }) {
  // Offline zones have no trustworthy count, so leave them out of the total.
  // If every zone is offline, still show the full capacity so the seat strip isn't empty.
  const live = zones.filter((z) => !z.stale);
  const count = live.reduce((s, z) => s + z.occupancy, 0);
  const capacity = (live.length ? live : zones).reduce((s, z) => s + z.capacity, 0);
  const status = live.length ? getStatus(count, capacity) : OFFLINE;
  const label = liveLabel(connection, zones.length - live.length, zones.length);

  return (
    <section className={`card hero status-${status.key}`} aria-label="Current occupancy">
      <div className="hero-top">
        <div>
          <p className="live"><span className={`live-dot${label.ok ? '' : ' off'}`} /> {label.text}</p>
          <p className="hero-count">
            <span className="hero-num">{live.length ? count : '-'}</span>
            <span className="hero-of">people of {capacity}</span>
          </p>
        </div>
        <div className="hero-status">
          <span className="status-word">{status.label}</span>
          {live.length > 0 && <span className="hero-pct">{Math.round(status.pct)}% full</span>}
        </div>
      </div>
      <SeatStrip count={count} capacity={capacity} />
      <div className="hero-foot">
        <StatRow stats={stats} />
      </div>
    </section>
  );
}
