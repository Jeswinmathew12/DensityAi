import React from 'react';
import { getStatus } from '../utils/status';

export default function ZoneTable({ zones }) {
  return (
    <div className="card">
      <h2>Zones</h2>
      <table className="zone-table">
        <thead>
          <tr><th>Zone</th><th>Count</th><th>Capacity</th><th>Status</th></tr>
        </thead>
        <tbody>
          {zones.map((z) => {
            const s = getStatus(z.occupancy, z.capacity);
            return (
              <tr key={z.id}>
                <td>{z.name}</td>
                <td>{z.occupancy}</td>
                <td>{z.capacity}</td>
                <td><span className={`badge status-${s.key}`}>{s.label}</span></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
