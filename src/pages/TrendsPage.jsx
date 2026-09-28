import React from 'react';
import OccupancyTrend from '../components/OccupancyTrend';
import TrafficChart from '../components/TrafficChart';

export default function TrendsPage({ zones, trends, traffic, stats }) {
  return (
    <>
      <h1>Trends</h1>
      <div className="kpi-row trends-stats">
        <div className="card kpi"><span className="kpi-label">Peak hour</span><span className="kpi-value small">{stats.peakHour}</span></div>
        <div className="card kpi"><span className="kpi-label">Avg occupancy</span><span className="kpi-value small">{stats.avgOccupancy}</span></div>
        <div className="card kpi"><span className="kpi-label">Visitors today</span><span className="kpi-value small">{stats.totalVisitors}</span></div>
      </div>
      <div className="stack">
        {zones.map((z) => (
          <OccupancyTrend key={z.id} data={trends[z.id]} title={`${z.name} - last 24h`} />
        ))}
        <TrafficChart data={traffic} />
      </div>
    </>
  );
}
