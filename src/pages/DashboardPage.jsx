import React, { useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import KpiCards from '../components/KpiCards';
import OccupancyTrend from '../components/OccupancyTrend';
import ZoneTable from '../components/ZoneTable';
import TrafficChart from '../components/TrafficChart';
import Insights from '../components/Insights';

function ZonePager({ zones, selectedIndex, onSelect, chartName }) {
  const previous = zones[(selectedIndex - 1 + zones.length) % zones.length];
  const next = zones[(selectedIndex + 1) % zones.length];

  return (
    <div className="zone-pager" role="group" aria-label={`Choose zone for ${chartName}`}>
      <button type="button" aria-label={`Previous zone: ${previous.name}`} onClick={() => onSelect(previous.id)}>
        <ChevronLeft size={18} aria-hidden />
      </button>
      <span className="zone-pager-count" aria-live="polite">
        {selectedIndex + 1} of {zones.length}
      </span>
      <button type="button" aria-label={`Next zone: ${next.name}`} onClick={() => onSelect(next.id)}>
        <ChevronRight size={18} aria-hidden />
      </button>
    </div>
  );
}

export default function DashboardPage({
  zones, trends, traffic, trafficByZone, stats, insights, connection, source,
}) {
  const [selectedTrendZoneId, setSelectedTrendZoneId] = useState(zones[0]?.id);
  const [selectedTrafficZoneId, setSelectedTrafficZoneId] = useState(zones[0]?.id);
  const isMock = source === 'mock';
  const trendIndex = Math.max(0, zones.findIndex((zone) => zone.id === selectedTrendZoneId));
  const trafficIndex = Math.max(0, zones.findIndex((zone) => zone.id === selectedTrafficZoneId));
  const trendZone = zones[trendIndex] || zones[0];
  const trafficZone = zones[trafficIndex] || zones[0];

  return (
    <>
      <div className="page-head">
        <h1>{isMock ? 'Student Union' : 'Occupancy'}</h1>
        {isMock && <span className="demo-label">Simulated demo data</span>}
      </div>
      <KpiCards zones={zones} stats={stats} connection={connection} />
      <div className="grid-2 dashboard-main-grid">
        <OccupancyTrend
          data={trends[trendZone.id]}
          title={`${trendZone.name} (last 24h)`}
          actions={(
            <ZonePager
              zones={zones}
              selectedIndex={trendIndex}
              onSelect={setSelectedTrendZoneId}
              chartName="occupancy trend"
            />
          )}
        />
        <ZoneTable zones={zones} />
      </div>
      <div className="grid-2">
        <TrafficChart
          data={trafficByZone?.[trafficZone.id] || []}
          zoneName={trafficZone.name}
          actions={(
            <ZonePager
              zones={zones}
              selectedIndex={trafficIndex}
              onSelect={setSelectedTrafficZoneId}
              chartName="traffic chart"
            />
          )}
        />
        <Insights items={insights} zones={zones} />
      </div>
    </>
  );
}
