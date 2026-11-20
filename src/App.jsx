import React from 'react';
import { LayoutDashboard, Users, BarChart3, Settings, Lock, ShoppingBag, Network } from 'lucide-react';
import useOccupancyData from './hooks/useOccupancyData';
import { API_URL } from './services/api';
import useHashRoute from './hooks/useHashRoute';
import DashboardPage from './pages/DashboardPage';
import ZonesPage from './pages/ZonesPage';
import TrendsPage from './pages/TrendsPage';
import SettingsPage from './pages/SettingsPage';
import AdminPage from './pages/AdminPage';
import StorePage from './pages/StorePage';
import SystemPage from './pages/SystemPage';

const NAV = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, page: DashboardPage },
  { id: 'zones', label: 'Zones', icon: Users, page: ZonesPage },
  { id: 'trends', label: 'Trends', icon: BarChart3, page: TrendsPage },
  { id: 'store', label: 'Store insights', icon: ShoppingBag, page: StorePage },
  { id: 'system', label: 'System', icon: Network, page: SystemPage },
  { id: 'settings', label: 'Settings', icon: Settings, page: SettingsPage },
  { id: 'admin', label: 'Admin', icon: Lock, page: AdminPage },
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
            <p className="kpi-sub">
              Start it with <code>npm run serve</code> (Jetson) or <code>npm run backend</code> (development).
            </p>
            {process.env.NODE_ENV === 'production' && (
              <p className="kpi-sub">
                If that address isn't the one in your browser's address bar, this build is stale. Rebuild it on
                the Jetson with <code>rm -rf build &amp;&amp; npm run serve</code>.
              </p>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
