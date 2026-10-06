import React from 'react';
import OccupancyTrend from '../components/OccupancyTrend';
import StatRow from '../components/StatRow';
import TrafficChart from '../components/TrafficChart';

export default function TrendsPage({ zones, trends, traffic, stats }) {
  return (
    <>
      <h1>Trends</h1>
      <div className="card stat-card"><StatRow stats={stats} /></div>
      <div className="stack">
        {zones.map((z) => (
          <OccupancyTrend key={z.id} data={trends[z.id]} title={`${z.name} - last 24h`} />
        ))}
        <TrafficChart data={traffic} />
      </div>
    </>
  );
}
