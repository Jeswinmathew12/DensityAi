import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

const AXIS = { fill: 'var(--text-muted)', fontSize: 12 };
const TIP = { border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'none', fontSize: 13 };

// Hours with occupancy null had no camera data; they are drawn as gaps, not as zero.
export default function OccupancyTrend({ data = [], title = 'Occupancy (last 24h)' }) {
  if (!data.some((d) => d.occupancy != null)) {
    return (
      <div className="card">
        <h2>{title}</h2>
        <p className="chart-empty">No occupancy data in the last 24 hours yet.</p>
      </div>
    );
  }
  return (
    <div className="card">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" interval={3} tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={32} />
          <Tooltip contentStyle={TIP} cursor={{ stroke: 'var(--text-muted)' }} />
          <Area type="monotone" dataKey="occupancy" stroke="var(--ink)" strokeWidth={2} fill="var(--ink)" fillOpacity={0.07} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
