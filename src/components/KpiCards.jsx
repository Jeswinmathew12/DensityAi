import React from 'react';
import { getStatus } from '../utils/status';
import SeatStrip from './SeatStrip';
import StatRow from './StatRow';

export default function KpiCards({ zones, stats }) {
  const count = zones.reduce((s, z) => s + z.occupancy, 0);
  const capacity = zones.reduce((s, z) => s + z.capacity, 0);
  const status = getStatus(count, capacity);

  return (
    <section className={`card hero status-${status.key}`} aria-label="Current occupancy">
      <div className="hero-top">
        <div>
          <p className="live"><span className="live-dot" /> Live now</p>
          <p className="hero-count">
            <span className="hero-num">{count}</span>
            <span className="hero-of">people of {capacity}</span>
          </p>
        </div>
        <div className="hero-status">
          <span className="status-word">{status.label}</span>
          <span className="hero-pct">{Math.round(status.pct)}% full</span>
        </div>
      </div>
      <SeatStrip count={count} capacity={capacity} />
      <div className="hero-foot">
        <StatRow stats={stats} />
      </div>
    </section>
  );
}
