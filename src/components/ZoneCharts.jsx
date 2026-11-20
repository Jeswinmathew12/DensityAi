import React from 'react';
import { ResponsiveContainer, PieChart, Pie, Cell, Tooltip } from 'recharts';
import { formatDwell } from './StoreKpis';

const TIP = { border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'none', fontSize: 13 };
const COLORS = ['var(--c1)', 'var(--c2)', 'var(--c3)', 'var(--c4)', 'var(--c5)', 'var(--c6)', 'var(--c7)', 'var(--c8)'];

// A donut with its legend beside it. Each slice keeps the color of its entity (fixed order),
// and the legend carries the numbers, so nothing relies on color alone.
function Donut({ title, subtitle, slices, empty }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      {subtitle && <p className="legend">{subtitle}</p>}
      {!slices.length ? (
        <p className="chart-empty">{empty}</p>
      ) : (
        <div className="donut">
          <ResponsiveContainer width="100%" height={210}>
            <PieChart>
              <Pie data={slices} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="92%"
                stroke="var(--surface)" strokeWidth={2} startAngle={90} endAngle={-270} isAnimationActive={false}>
                {slices.map((s) => <Cell key={s.name} fill={s.color} />)}
              </Pie>
              <Tooltip contentStyle={TIP} formatter={(v, n, p) => [`${v.toLocaleString()} (${p.payload.pct}%)`, n]} />
            </PieChart>
          </ResponsiveContainer>
          <ul className="donut-legend">
            {slices.map((s) => (
              <li key={s.name}>
                <i style={{ background: s.color }} aria-hidden />
                <span>{s.name}</span>
                <b>{s.pct}%</b>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// Where shoppers spend their visits. Colors follow the zone's position in the site's zone list.
export function ZoneSharePie({ share, zones }) {
  const order = zones.filter((z) => z.role !== 'entrance').map((z) => z.id);
  const slices = share.map((s) => ({
    name: s.name, value: s.visits, pct: s.sharePct, color: COLORS[Math.max(0, order.indexOf(s.zoneId)) % COLORS.length],
  }));
  return <Donut title="Where shoppers go" subtitle="Share of zone visits" slices={slices}
    empty="No zone visits in this period yet." />;
}

// How long each zone visit lasted: walked past, browsed, shopped, lingered.
export function DwellPie({ buckets }) {
  const total = buckets.reduce((s, b) => s + b.count, 0);
  const slices = buckets.map((b, i) => ({
    name: b.label, value: b.count, pct: total ? Math.round((100 * b.count) / total) : 0, color: COLORS[(i + 4) % COLORS.length],
  }));
  return <Donut title="How long shoppers stay" subtitle="Time spent per zone visit" slices={slices}
    empty="No dwell times yet. They need the tracker (start the pipeline with --tracker)." />;
}

// One row per zone: how many shoppers reach it, how long they stay, how crowded it gets.
export function ZoneScorecard({ zones }) {
  return (
    <div className="card">
      <h2>Zone scorecard</h2>
      <div className="table-scroll">
        <table className="zone-table score-table">
          <thead>
            <tr>
              <th>Zone</th><th>Visits</th><th>Reach</th><th>Avg stay</th><th>Stopped 30 s+</th><th>Peak</th><th>Alerts</th>
            </tr>
          </thead>
          <tbody>
            {zones.map((z) => (
              <tr key={z.id}>
                <td>{z.name}</td>
                <td>{z.visits == null ? '-' : z.visits.toLocaleString()}</td>
                <td>{z.reachPct == null ? '-' : `${z.reachPct}%`}</td>
                <td>{z.avgDwellSec == null ? '-' : formatDwell(z.avgDwellSec)}</td>
                <td>{z.engagedPct == null ? '-' : `${z.engagedPct}%`}</td>
                <td>{z.peakOccupancy == null ? '-' : `${z.peakOccupancy} of ${z.capacity}`}</td>
                <td>{z.alerts || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
