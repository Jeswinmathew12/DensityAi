import React from 'react';
import SeatStrip from '../components/SeatStrip';
import { getZoneStatus } from '../utils/status';

const time = (iso) => new Date(iso).toLocaleTimeString();

export default function ZonesPage({ zones }) {
  return (
    <>
      <h1>Zones</h1>
      <div className="zone-cards">
        {zones.map((z) => {
          const s = getZoneStatus(z);
          return (
            <div key={z.id} className="card zone-card">
              <div className="zone-card-head">
                <h2>{z.name}</h2>
                <span className={`badge status-${s.key}`}>{s.label}</span>
              </div>
              <p className="zone-count">
                <span className={`zone-num status-${s.key}-text`}>{z.stale ? '-' : z.occupancy}</span>
                <span className="kpi-sub">
                  {z.stale ? `of ${z.capacity} · no live count` : `of ${z.capacity} · ${Math.round(s.pct)}% full`}
                </span>
              </p>
              <SeatStrip count={z.stale ? 0 : z.occupancy} capacity={z.capacity} size="sm" />
              <p className="kpi-sub zone-meta">
                {z.cameras} camera{z.cameras === 1 ? '' : 's'},{' '}
                {!z.stale
                  ? `updated ${time(z.lastUpdated)}`
                  : z.lastUpdated
                    ? `camera offline since ${time(z.lastUpdated)}`
                    : 'no data from camera yet'}
              </p>
            </div>
          );
        })}
      </div>
    </>
  );
}
