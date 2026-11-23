import React from 'react';
import { CameraOff, Gauge, TrendingUp } from 'lucide-react';
import { getZoneStatus } from '../utils/status';

const CATEGORIES = {
  capacity: { label: 'Capacity watch', Icon: Gauge, className: 'capacity' },
  data: { label: 'Data quality', Icon: CameraOff, className: 'data' },
  demand: { label: 'Demand pattern', Icon: TrendingUp, className: 'demand' },
};

function getCapacityInsight(zone) {
  const status = getZoneStatus(zone);
  if (status.key !== 'busy') return null;

  const count = Math.round(zone.occupancy);
  const capacity = Math.round(zone.capacity);
  const unit = capacity === 1 ? 'person' : 'people';
  const title = status.pct > 100
    ? `${zone.name} is over capacity`
    : status.pct === 100
      ? `${zone.name} is at capacity`
      : `${zone.name} is nearing capacity`;

  return {
    id: `capacity-${zone.id}`,
    category: 'capacity',
    title,
    detail: `${count} of ${capacity} ${unit}; ${Math.round(status.pct)}% full right now.`,
    score: status.pct,
  };
}

function getDataInsights(zones, items) {
  const offlineZones = zones.filter((zone) => getZoneStatus(zone).key === 'offline');
  if (!offlineZones.length) return items.filter((item) => item.category === 'data').slice(0, 1);

  if (offlineZones.length === 1) {
    const [zone] = offlineZones;
    const lastReport = zone.lastUpdated
      ? new Date(zone.lastUpdated).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
      : null;
    return [{
      id: `data-offline-${zone.id}`,
      category: 'data',
      title: `No recent count from ${zone.name}`,
      detail: lastReport
        ? `Last report received at ${lastReport}.`
        : 'No camera reading has been received yet.',
    }];
  }

  const names = offlineZones.slice(0, 2).map((zone) => zone.name);
  const more = offlineZones.length - names.length;
  return [{
    id: 'data-offline-summary',
    category: 'data',
    title: `${offlineZones.length} zones have stale counts`,
    detail: `${names.join(', ')}${more ? `, and ${more} more` : ''}.`,
  }];
}

export default function Insights({ items = [], zones = [] }) {
  const capacity = zones
    .map(getCapacityInsight)
    .filter(Boolean)
    .sort((a, b) => b.score - a.score)
    .slice(0, 1);
  const data = getDataInsights(zones, items);
  const demand = items.filter((item) => item.category === 'demand');
  const visibleItems = [...capacity, ...data, ...demand].slice(0, 3);

  return (
    <section className="card" aria-labelledby="insights-title">
      <h2 id="insights-title">What stands out</h2>
      <p className="insights-summary">Live capacity watches and patterns from recent counts.</p>
      {visibleItems.length ? (
        <ul className="insight-list">
          {visibleItems.map((item) => {
            const { label, Icon, className } = CATEGORIES[item.category];
            return (
              <li className="insight-item" key={item.id}>
                <span className={`insight-icon insight-${className}`} aria-hidden="true">
                  <Icon size={17} />
                </span>
                <div className="insight-copy">
                  <span className={`insight-category insight-category-${className}`}>{label}</span>
                  <p className="insight-title">{item.title}</p>
                  <p className="insight-detail">{item.detail}</p>
                </div>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="insights-empty">Demand peaks and camera-data gaps will appear as data builds.</p>
      )}
    </section>
  );
}
