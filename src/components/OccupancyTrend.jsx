import React from 'react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';

const AXIS = { fill: 'var(--text-muted)', fontSize: 12 };
const TIP = { border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'none', fontSize: 13 };

// An hour with no data on either side has no line to sit on, so it gets a dot instead.
const isolated = (data, i) =>
  data[i]?.occupancy != null && data[i - 1]?.occupancy == null && data[i + 1]?.occupancy == null;

// Hours with occupancy null had no camera data; they are drawn as gaps, not as zero.
export default function OccupancyTrend({ data = [], title = 'Occupancy (last 24h)', actions }) {
  const dot = ({ index, cx, cy }) =>
    isolated(data, index) ? <circle key={index} cx={cx} cy={cy} r={4} fill="var(--ink)" /> : <g key={index} />;
  const heading = (
    <div className="trend-heading">
      <div>
        <h2>{title}</h2>
        <p className="chart-description">Each point shows how many people were in this zone at that hour.</p>
      </div>
      {actions}
    </div>
  );
  if (!data.some((d) => d.occupancy != null)) {
    return (
      <div className="card">
        {heading}
        <p className="chart-empty">No occupancy data in the last 24 hours yet.</p>
      </div>
    );
  }
  return (
    <div className="card">
      {heading}
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 10, left: 8 }}>
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
            domain={[0, 'auto']}
            tick={AXIS}
            tickLine={false}
            axisLine={false}
            width={52}
            label={{ value: 'People in zone', angle: -90, position: 'insideLeft', ...AXIS }}
          />
          <Tooltip
            labelFormatter={(label) => `At ${label}`}
            formatter={(value) => [`${value} ${Number(value) === 1 ? 'person' : 'people'}`, 'Occupancy']}
            contentStyle={TIP}
            cursor={{ stroke: 'var(--text-muted)' }}
          />
          <Area
            type="monotone"
            dataKey="occupancy"
            name="Occupancy"
            stroke="var(--ink)"
            strokeWidth={2}
            fill="var(--ink)"
            fillOpacity={0.07}
            dot={dot}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
