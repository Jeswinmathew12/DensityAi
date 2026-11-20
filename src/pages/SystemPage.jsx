import React from 'react';
import SystemFlow from '../components/SystemFlow';
import { useSystemStatus } from '../hooks/useStoreAnalytics';
import { API_URL } from '../services/api';
import { DATA_SOURCE } from '../hooks/useOccupancyData';

// How the product fits together, live: camera -> collector -> database -> web service -> dashboard.
export default function SystemPage() {
  const { data, error } = useSystemStatus();
  return (
    <>
      <h1>System</h1>
      {data ? <SystemFlow status={data} /> : (
        <div className="card"><p className="kpi-sub">{error ? `Can't reach the web service: ${error.message}` : 'Loading…'}</p></div>
      )}
      <div className="grid-2 system-notes">
        <div className="card">
          <h2>Why it's built this way</h2>
          <ul className="insights">
            <li><span>The Jetson only counts. It sends numbers to the collector, so the video never leaves the store.</span></li>
            <li><span>Every count, entry, exit, visit length and alert is one row in a PostgreSQL events table, so history is kept and can be analyzed later.</span></li>
            <li><span>The dashboard only talks to the web service. Cameras, database and dashboard can each move to other machines (or the cloud) without changing the others.</span></li>
          </ul>
        </div>
        <div className="card">
          <h2>REST API</h2>
          <p className="kpi-sub">
            {DATA_SOURCE === 'live' ? (
              <>Every number on this dashboard comes from the web service. Try it: <a href={`${API_URL}/docs`} target="_blank" rel="noreferrer">{API_URL}/docs</a></>
            ) : 'Showing sample status. Run npm run start:live to use the web service.'}
          </p>
          <ul className="insights api-list">
            <li><code>GET /api/sites</code><span>stores and their zones</span></li>
            <li><code>GET /api/sites/&#123;id&#125;/analytics</code><span>busiest times, dwell, recommendations</span></li>
            <li><code>GET /api/sites/&#123;id&#125;/events</code><span>raw events</span></li>
            <li><code>GET /api/zones</code>, <code>WS /ws/live</code><span>live counts</span></li>
          </ul>
        </div>
      </div>
    </>
  );
}
