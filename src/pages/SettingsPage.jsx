import React from 'react';
import { THRESHOLDS } from '../utils/status';

// Read-only for now: thresholds live in src/utils/status.js and zones come from the data source.
export default function SettingsPage({ zones }) {
  return (
    <>
      <h1>Settings</h1>
      <div className="stack">
        <div className="card">
          <h2>Status thresholds</h2>
          <ul className="insights">
            <li><span className="badge status-available">Available</span> under {THRESHOLDS.moderate}% of capacity</li>
            <li><span className="badge status-moderate">Moderate</span> {THRESHOLDS.moderate}% to {THRESHOLDS.busy}%</li>
            <li><span className="badge status-busy">Busy</span> over {THRESHOLDS.busy}%</li>
          </ul>
        </div>
        <div className="card">
          <h2>Zones and cameras</h2>
          <table className="zone-table">
            <thead><tr><th>Zone</th><th>Capacity</th><th>Cameras</th></tr></thead>
            <tbody>
              {zones.map((z) => (
                <tr key={z.id}><td>{z.name}</td><td>{z.capacity}</td><td>{z.cameras}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="card">
          <h2>Data source</h2>
          <p className="kpi-sub">Simulated data. Live Jetson feed not connected yet.</p>
        </div>
      </div>
    </>
  );
}
