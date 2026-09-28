import React from 'react';
import { LayoutDashboard, Users, BarChart3, Settings } from 'lucide-react';
import useOccupancyData from './hooks/useOccupancyData';
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
        <div className="brand">DensityAI</div>
        <nav>
          {NAV.map(({ id, label, icon: Icon }) => (
            <a key={id} className={`nav-item${id === active.id ? ' active' : ''}`} href={`#/${id}`}>
              <Icon size={18} /> {label}
            </a>
          ))}
        </nav>
      </aside>
      <main className="content">
        <Page {...data} />
      </main>
    </div>
  );
}
