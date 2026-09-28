import React from 'react';
import { getStatus } from '../utils/status';

export default function KpiCards({ zones, stats }) {
  const count = zones.reduce((s, z) => s + z.occupancy, 0);
  const capacity = zones.reduce((s, z) => s + z.capacity, 0);
  const status = getStatus(count, capacity);

  return (
    <div className="kpi-row">
      <div className={`card kpi kpi-live status-${status.key}`}>
        <span className="kpi-label">Right now</span>
        <span className="kpi-value">{count}</span>
        <span className="kpi-sub">{status.label} - {Math.round(status.pct)}% of {capacity}</span>
      </div>
      <div className="card kpi">
        <span className="kpi-label">Peak hour</span>
        <span className="kpi-value small">{stats.peakHour}</span>
      </div>
      <div className="card kpi">
        <span className="kpi-label">Avg occupancy</span>
        <span className="kpi-value small">{stats.avgOccupancy}</span>
      </div>
      <div className="card kpi">
        <span className="kpi-label">Visitors today</span>
        <span className="kpi-value small">{stats.totalVisitors}</span>
      </div>
    </div>
  );
}
