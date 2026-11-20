import React from 'react';

// Sequential blue ramp, light to dark (CSS variables --seq-1 .. --seq-7 in App.css).
const STEPS = 7;
const step = (v, max) => (v == null || !max ? 0 : Math.min(STEPS, 1 + Math.floor((v / max) * (STEPS - 0.001))));

// Average people in the store for each weekday and hour: when to staff up, when to restock.
export default function BusyHeatmap({ rows }) {
  const hours = rows[0]?.cells || [];
  const max = Math.max(0, ...rows.flatMap((r) => r.cells.map((c) => c.value || 0)));
  return (
    <div className="card">
      <h2>Busiest times</h2>
      <p className="legend">Average shoppers in the store, by day and hour</p>
      {!hours.length ? (
        <p className="chart-empty">No occupancy data in this period yet.</p>
      ) : (
        <div className="heatmap-wrap">
          <table className="heatmap">
            <thead>
              <tr>
                <th aria-label="Day" />
                {hours.map((c) => (
                  <th key={c.hour} scope="col">{c.hour % 3 === 0 ? c.label : ''}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.day}>
                  <th scope="row">{r.day}</th>
                  {r.cells.map((c) => (
                    <td
                      key={c.hour}
                      className={`seq-${step(c.value, max)}`}
                      title={`${r.day} ${c.label}: ${c.value == null ? 'closed / no data' : `${c.value} shoppers`}`}
                    >
                      <span className="sr-only">{c.value ?? 'no data'}</span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="heat-scale" aria-hidden>
            <span>Quiet</span>
            {Array.from({ length: STEPS }, (_, i) => <i key={i} className={`seq-${i + 1}`} />)}
            <span>Busy ({Math.round(max)})</span>
          </div>
        </div>
      )}
    </div>
  );
}
