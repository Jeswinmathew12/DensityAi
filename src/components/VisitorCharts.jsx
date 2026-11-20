import React from 'react';
import {
  ResponsiveContainer, BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';

const AXIS = { fill: 'var(--text-muted)', fontSize: 12 };
const TIP = { border: '1px solid var(--border)', borderRadius: 8, boxShadow: 'none', fontSize: 13 };
const has = (data) => data.some((d) => d.visitors != null);

function Empty({ title }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="chart-empty">No visitor counts in this period yet. They need line crossing (--tracker).</p>
    </div>
  );
}

// Average visitors on each day of the week.
export function VisitorsByWeekday({ data }) {
  const title = 'Visitors by day of the week';
  if (!has(data)) return <Empty title={title} />;
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="legend">Average shoppers per day</p>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} barCategoryGap="22%">
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="day" tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={40} />
          <Tooltip contentStyle={TIP} cursor={{ fill: 'var(--bg)' }} />
          <Bar dataKey="visitors" name="Visitors" fill="var(--c1)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Average visitors arriving in each hour of the day.
export function VisitorsByHour({ data }) {
  const title = 'Visitors by hour';
  if (!has(data)) return <Empty title={title} />;
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="legend">Average shoppers walking in each hour</p>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} barCategoryGap="15%">
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" interval={2} tick={AXIS} tickLine={false} axisLine={{ stroke: 'var(--border)' }} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={40} />
          <Tooltip contentStyle={TIP} cursor={{ fill: 'var(--bg)' }} />
          <Bar dataKey="visitors" name="Visitors" fill="var(--c2)" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// Visitors per day across the period: is traffic growing?
export function DailyVisitors({ data }) {
  const title = 'Daily visitors';
  if (!has(data)) return <Empty title={title} />;
  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="legend">Today is still under way, so its number is partial</p>
      <ResponsiveContainer width="100%" height={230}>
        <LineChart data={data}>
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis dataKey="label" interval="preserveStartEnd" minTickGap={24} tick={AXIS} tickLine={false}
            axisLine={{ stroke: 'var(--border)' }} />
          <YAxis tick={AXIS} tickLine={false} axisLine={false} width={40} />
          <Tooltip contentStyle={TIP} labelFormatter={(l, p) => `${p?.[0]?.payload.weekday || ''} ${l}`} />
          <Line type="monotone" dataKey="visitors" name="Visitors" stroke="var(--c3)" strokeWidth={2}
            dot={false} activeDot={{ r: 5 }} connectNulls={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
