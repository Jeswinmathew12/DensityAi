import React from 'react';
import SeatStrip from '../components/SeatStrip';
import { getStatus } from '../utils/status';

export default function ZonesPage({ zones }) {
  return (
    <>
      <h1>Zones</h1>
      <div className="zone-cards">
        {zones.map((z) => {
          const s = getStatus(z.occupancy, z.capacity);
          return (
            <div key={z.id} className="card zone-card">
              <div className="zone-card-head">
                <h2>{z.name}</h2>
                <span className={`badge status-${s.key}`}>{s.label}</span>
              </div>
              <p className="zone-count">
                <span className={`zone-num status-${s.key}-text`}>{z.occupancy}</span>
                <span className="kpi-sub">of {z.capacity} · {Math.round(s.pct)}% full</span>
              </p>
              <SeatStrip count={z.occupancy} capacity={z.capacity} size="sm" />
              <p className="kpi-sub zone-meta">
                {z.cameras} camera{z.cameras === 1 ? '' : 's'}, updated {new Date(z.lastUpdated).toLocaleTimeString()}
              </p>
            </div>
          );
        })}
      </div>
    </>
  );
}
