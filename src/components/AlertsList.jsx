import React from 'react';
import { AlertTriangle } from 'lucide-react';

const when = (iso) =>
  new Date(iso).toLocaleString('en-US', { weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });

// Crowding alerts: a zone reached the alert level set for it.
export default function AlertsList({ alerts }) {
  return (
    <div className="card">
      <h2>Recent alerts</h2>
      {alerts.length ? (
        <ul className="insights alerts">
          {alerts.slice(0, 6).map((a) => (
            <li key={`${a.time}-${a.zoneId}`}>
              <AlertTriangle size={16} aria-hidden />
              <span><b>{when(a.time)}</b><br />{a.text}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="kpi-sub">No crowding alerts in this period.</p>
      )}
    </div>
  );
}
