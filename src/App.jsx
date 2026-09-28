import React from 'react';
import { LayoutDashboard, Users, BarChart3, Settings } from 'lucide-react';
import useOccupancyData from './hooks/useOccupancyData';
import KpiCards from './components/KpiCards';
import OccupancyTrend from './components/OccupancyTrend';
import ZoneTable from './components/ZoneTable';
import TrafficChart from './components/TrafficChart';
import Insights from './components/Insights';

const NAV = [
  { label: 'Dashboard', icon: LayoutDashboard },
  { label: 'Zones', icon: Users },
  { label: 'Trends', icon: BarChart3 },
  { label: 'Settings', icon: Settings },
];

export default function App() {
  const { zones, trend, traffic, stats, insights } = useOccupancyData();

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">DensityAI</div>
        <nav>
          {NAV.map(({ label, icon: Icon }, i) => (
            <a key={label} className={`nav-item${i === 0 ? ' active' : ''}`} href="#top">
              <Icon size={18} /> {label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="content" id="top">
        <h1>Occupancy Insight</h1>
        <KpiCards zones={zones} stats={stats} />
        <div className="grid-2">
          <OccupancyTrend data={trend} />
          <ZoneTable zones={zones} />
        </div>
        <div className="grid-2">
          <TrafficChart data={traffic} />
          <Insights items={insights} />
        </div>
      </main>
    </div>
  );
}
