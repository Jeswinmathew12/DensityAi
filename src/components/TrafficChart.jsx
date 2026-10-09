import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';

const AXIS = { fill: 'var(--text-muted)', fontSize: 12 };
const TIP = { border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'none', fontSize: 13 };

export default function TrafficChart({ data }) {
  if (!data.some((d) => d.entries || d.exits)) {
    return (
      <div className="card">
        <h2>Traffic in and out</h2>
        <p className="chart-empty">No entries or exits recorded in the last 24 hours.</p>
      </div>
    );
  }
  // null means no camera data that hour; keep it null so it isn't drawn as zero.
  const shaped = data.map((d) => ({ ...d, exits: d.exits == null ? null : -d.exits }));
  return (
    <div className="card">
      <h2>Traffic in and out</h2>
      <p className="legend"><i className="sw in" /> Entered <i className="sw out" /> Left</p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={shaped} stackOffset="sign">
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" interval={3} tick={AXIS} tickLine={false} axisLine={false} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={32} tickFormatter={(v) => Math.abs(v)} />
          <Tooltip formatter={(v, n) => [Math.abs(v), n]} contentStyle={TIP} cursor={{ fill: 'var(--bg)' }} />
          <ReferenceLine y={0} stroke="var(--ink)" />
          <Bar dataKey="entries" name="Entered" stackId="t" fill="var(--in)" />
          <Bar dataKey="exits" name="Left" stackId="t" fill="var(--out)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
