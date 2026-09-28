import React from 'react';
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
              <div className={`kpi-value status-${s.key}-text`}>{z.occupancy}</div>
              <div className="kpi-sub">of {z.capacity} capacity ({Math.round(s.pct)}%)</div>
              <div className="meter">
                <div className={`meter-fill status-${s.key}`} style={{ width: `${Math.min(100, s.pct)}%` }} />
              </div>
              <div className="kpi-sub">
                {z.cameras} camera{z.cameras === 1 ? '' : 's'} - updated {new Date(z.lastUpdated).toLocaleTimeString()}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
