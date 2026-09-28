import React from 'react';
import KpiCards from '../components/KpiCards';
import OccupancyTrend from '../components/OccupancyTrend';
import ZoneTable from '../components/ZoneTable';
import TrafficChart from '../components/TrafficChart';
import Insights from '../components/Insights';

export default function DashboardPage({ zones, trends, traffic, stats, insights }) {
  return (
    <>
      <h1>Occupancy Insight</h1>
      <KpiCards zones={zones} stats={stats} />
      <div className="grid-2">
        <OccupancyTrend data={trends[zones[0].id]} />
        <ZoneTable zones={zones} />
      </div>
      <div className="grid-2">
        <TrafficChart data={traffic} />
        <Insights items={insights} />
      </div>
    </>
  );
}
