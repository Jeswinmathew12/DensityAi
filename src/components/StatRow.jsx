import React from 'react';

export default function StatRow({ stats }) {
  const items = [
    ['Peak hour', stats.peakHour],
    ['Average occupancy', stats.avgOccupancy],
    ['Visitors today', stats.totalVisitors],
  ];
  return (
    <dl className="stat-row">
      {items.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
