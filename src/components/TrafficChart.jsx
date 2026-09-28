import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';

export default function TrafficChart({ data }) {
  const shaped = data.map((d) => ({ ...d, exits: -d.exits }));
  return (
    <div className="card">
      <h2>Traffic in / out</h2>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={shaped} stackOffset="sign">
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" interval={3} />
          <YAxis />
          <Tooltip formatter={(v) => Math.abs(v)} />
          <ReferenceLine y={0} stroke="var(--text-muted)" />
          <Bar dataKey="entries" stackId="t" fill="var(--green)" />
          <Bar dataKey="exits" stackId="t" fill="var(--red)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
