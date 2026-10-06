import React from 'react';
import { LayoutDashboard, Users, BarChart3, Settings } from 'lucide-react';
import useOccupancyData from './hooks/useOccupancyData';
import { API_URL } from './services/api';
import useHashRoute from './hooks/useHashRoute';
import DashboardPage from './pages/DashboardPage';
import ZonesPage from './pages/ZonesPage';
import TrendsPage from './pages/TrendsPage';
import SettingsPage from './pages/SettingsPage';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, page: DashboardPage },
  { id: 'zones', label: 'Zones', icon: Users, page: ZonesPage },
  { id: 'trends', label: 'Trends', icon: BarChart3, page: TrendsPage },
  { id: 'settings', label: 'Settings', icon: Settings, page: SettingsPage },
];

export default function App() {
  const data = useOccupancyData();
  const route = useHashRoute();
  const active = NAV.find((n) => n.id === route) || NAV[0];
  const Page = active.page;

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark" aria-hidden><i /><i /><i /><i /></span>DensityAI</div>
        <nav>
          {NAV.map(({ id, label, icon: Icon }) => (
            <a key={id} className={`nav-item${id === active.id ? ' active' : ''}`} href={`#/${id}`}>
              <Icon size={18} aria-hidden /> {label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="content">
        {data.zones.length ? (
          <Page {...data} />
        ) : (
          // Live mode before the backend's first message.
          <div className="card">
            <p className="live"><span className="live-dot off" /> Connecting to the backend at {API_URL}…</p>
            <p className="kpi-sub">Start it with <code>npm run backend</code>.</p>
          </div>
        )}
      </main>
    </div>
  );
}
