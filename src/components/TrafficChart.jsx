import React from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, ReferenceLine } from 'recharts';

const AXIS = { fill: 'var(--text-muted)', fontSize: 12 };
const TIP = { border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'none', fontSize: 13 };

export default function TrafficChart({ data = [], zoneName, actions }) {
  const title = zoneName ? `${zoneName} traffic` : 'All zones traffic';
  const description = zoneName
    ? 'Last 24 hours. Above zero: entered this zone; below zero: left it.'
    : 'Last 24 hours. Combined entries are above zero; exits are below.';
  const emptyMessage = zoneName
    ? `No crossing counts for ${zoneName} yet. Line-crossing detection may be off.`
    : 'No crossing counts across zones yet. Line-crossing detection may be off.';

  const heading = (
    <div className="trend-heading">
      <div>
        <h2>{title}</h2>
        <p className="chart-description">{description}</p>
      </div>
      {actions}
    </div>
  );

  if (!data.some((d) => d.entries || d.exits)) {
    return (
      <div className="card">
        {heading}
        <p className="chart-empty">{emptyMessage}</p>
      </div>
    );
  }
  const shaped = data.map((d) => ({ ...d, exits: d.exits == null ? null : -d.exits }));
  return (
    <div className="card">
      {heading}
      <p className="legend"><i className="sw in" /> Entered <i className="sw out" /> Left</p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={shaped} stackOffset="sign" margin={{ top: 8, right: 8, bottom: 10, left: 8 }}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="label"
            interval={3}
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            height={44}
            label={{ value: 'Hour of day', position: 'insideBottom', offset: -8, ...AXIS }}
          />
          <YAxis
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            width={52}
            label={{ value: 'People per hour', angle: -90, position: 'insideLeft', ...AXIS }}
          />
          <Tooltip
            labelFormatter={(label) => `At ${label}`}
            formatter={(value, name) => [`${Math.abs(value)} people`, name]}
            contentStyle={TIP}
            cursor={{ fill: 'var(--bg)' }}
          />
          <ReferenceLine y={0} stroke="var(--ink)" />
          <Bar dataKey="entries" name="Entered this zone" stackId="t" fill="var(--in)" />
          <Bar dataKey="exits" name="Left this zone" stackId="t" fill="var(--out)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
