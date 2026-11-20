import React from 'react';

const dash = (v, fmt = (x) => x.toLocaleString()) => (v == null ? '-' : fmt(v));
export const formatDwell = (s) => (s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s`);

// Headline numbers for the selected period. Values are null when there's no data yet.
export default function StoreKpis({ kpis, days }) {
  const change = kpis.visitorsChangePct;
  const tiles = [
    { label: `Visitors, last ${days} days`, value: dash(kpis.visitors) },
    {
      label: 'Visitors per day',
      value: dash(kpis.visitorsPerDay),
      sub: change == null ? null : `${change >= 0 ? '+' : ''}${change}% vs the week before`,
      tone: change == null ? null : change >= 0 ? 'up' : 'down',
    },
    { label: 'Busiest hour', value: dash(kpis.busiest, String) },
    { label: 'Average time in a zone', value: dash(kpis.avgDwellSec, formatDwell) },
    { label: 'Reached checkout', value: dash(kpis.conversionPct, (v) => `${v}%`) },
    { label: 'Crowding alerts', value: dash(kpis.alerts) },
  ];
  return (
    <div className="kpi-grid">
      {tiles.map((t) => (
        <div className="card kpi-tile" key={t.label}>
          <p className="kpi-label">{t.label}</p>
          <p className="kpi-value">{t.value}</p>
          {t.sub && <p className={`kpi-delta ${t.tone}`}>{t.sub}</p>}
        </div>
      ))}
    </div>
  );
}
