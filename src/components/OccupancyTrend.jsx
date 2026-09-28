import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

export default function OccupancyTrend({ data, title = 'Occupancy (last 24h)' }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={240}>
        <AreaChart data={data}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" interval={3} />
          <YAxis />
          <Tooltip />
          <Area type="monotone" dataKey="occupancy" stroke="var(--blue)" fill="var(--blue)" fillOpacity={0.15} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
