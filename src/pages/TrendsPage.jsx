import React, { useState } from 'react';
import { getStatus } from '../utils/status';
import ZoneHeatmap from '../components/ZoneHeatmap';

const METRICS = [
  { id: 'occupancy', label: 'Capacity use' },
  { id: 'entries', label: 'Entries' },
  { id: 'exits', label: 'Exits' },
];

function formatHour(hour) {
  const value = Number(hour);
  return `${value % 12 || 12}:00 ${value < 12 ? 'AM' : 'PM'}`;
}

function getZonePeak(zone, points) {
  return points
    .filter((point) => point.occupancy != null)
    .reduce((peak, point) => {
      const status = getStatus(point.occupancy, zone.capacity);
      return !peak || status.pct > peak.status.pct
        ? { point, status }
        : peak;
    }, null);
}

function getDemandSummary(zones, trends) {
  const firstZoneHours = zones.length ? trends[zones[0].id] || [] : [];
  const buildingPeak = firstZoneHours.reduce((peak, point) => {
    const readings = zones.map((zone) =>
      (trends[zone.id] || []).find((item) => item.hour === point.hour)?.occupancy
    );
    if (readings.some((value) => value == null)) return peak;
    const total = readings.reduce((sum, value) => sum + value, 0);
    return !peak || total > peak.total ? { hour: point.hour, total } : peak;
  }, null);
  const zonePeaks = zones
    .map((zone) => {
      const points = trends[zone.id] || [];
      return { zone, peak: getZonePeak(zone, points) };
    })
    .filter((item) => item.peak)
    .sort((a, b) => b.peak.status.pct - a.peak.status.pct);

  return {
    buildingPeak,
    pressuredZones: zonePeaks.slice(0, 3),
  };
}

export default function TrendsPage({ zones = [], trends = {}, trafficByZone = {} }) {
  const [selectedZoneId, setSelectedZoneId] = useState(zones[0]?.id);
  const [selectedHour, setSelectedHour] = useState(null);
  const [metric, setMetric] = useState('occupancy');
  const summary = getDemandSummary(zones, trends);
  const selectedZone = zones.find((zone) => zone.id === selectedZoneId) || zones[0];
  const selectedTrend = selectedZone ? trends[selectedZone.id] || [] : [];
  const selectedPoint = selectedTrend.find((point) => point.hour === selectedHour)
    || selectedTrend[selectedTrend.length - 1]
    || null;
  const selectedTraffic = selectedZone ? trafficByZone[selectedZone.id] || [] : [];
  const trafficPoint = selectedPoint
    ? selectedTraffic.find((point) => point.hour === selectedPoint.hour)
    : null;
  const selectedValue = metric === 'occupancy'
    ? selectedPoint?.occupancy ?? null
    : trafficPoint?.[metric] ?? null;
  const selectedStatus = metric === 'occupancy' && selectedValue != null
    ? getStatus(selectedValue, selectedZone.capacity)
    : null;
  const selectedPeak = selectedZone ? getZonePeak(selectedZone, selectedTrend) : null;
  const selectedUnit = metric === 'occupancy'
    ? 'people'
    : metric === 'entries'
      ? selectedValue === 1 ? 'entry' : 'entries'
      : selectedValue === 1 ? 'exit' : 'exits';

  const selectCell = (zoneId, hour) => {
    setSelectedZoneId(zoneId);
    if (hour != null) setSelectedHour(hour);
  };

  return (
    <div className="trends-page">
      <header className="trends-page-header">
        <div>
          <h1>Demand &amp; capacity</h1>
          <p>See when and where occupancy approaches zone capacity.</p>
        </div>
        <span className="trends-period">Last 24 hours</span>
      </header>

      <section className="trends-summary" aria-label="Demand summary">
        <article className="trends-summary-card trends-pressure-card">
          <div className="trends-pressure-header">
            <div>
              <span className="trends-summary-label">Peak occupancy by zone</span>
              <p className="trends-pressure-description">
                Each zone’s highest hourly reading, compared with its capacity.
              </p>
            </div>
            <div className="trends-building-peak">
              <span className="trends-summary-label">Busiest building hour</span>
              <strong>{summary.buildingPeak ? formatHour(summary.buildingPeak.hour) : '—'}</strong>
              <span className="trends-summary-note">
                {summary.buildingPeak
                  ? `${summary.buildingPeak.total} people across all zones`
                  : 'No shared hourly readings'}
              </span>
            </div>
          </div>
          {summary.pressuredZones.length ? (
            <ol className="trends-pressure-list" aria-label="Top zones by peak occupancy">
              {summary.pressuredZones.map(({ zone, peak }, index) => {
                const { point, status } = peak;
                const percentage = Math.round(status.pct);
                return (
                  <li className="trends-pressure-item" key={zone.id}>
                    <span className="trends-pressure-rank" aria-hidden="true">{index + 1}</span>
                    <div className="trends-pressure-content">
                      <div className="trends-pressure-heading">
                        <strong>{zone.name}</strong>
                        <span>{percentage}%</span>
                      </div>
                      <div
                        className="trends-pressure-meter"
                        role="meter"
                        aria-label={`${zone.name} peak occupancy`}
                        aria-valuemin={0}
                        aria-valuemax={100}
                        aria-valuenow={Math.min(status.pct, 100)}
                        aria-valuetext={`${point.occupancy} of ${zone.capacity} people, ${percentage}% of capacity`}
                      >
                        <span
                          className={`trends-pressure-fill trends-pressure-${status.key}`}
                          style={{ width: `${Math.min(status.pct, 100)}%` }}
                        />
                      </div>
                      <p>
                        {point.occupancy} of {zone.capacity} people at {formatHour(point.hour)}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ol>
          ) : (
            <p className="trends-summary-note">No occupancy readings for this period.</p>
          )}
        </article>
      </section>

      <div className="trends-explorer">
        <section className="card trends-heatmap-card" aria-labelledby="trends-heatmap-title">
          <div className="trends-section-heading">
            <div>
              <h2 id="trends-heatmap-title">Occupancy by zone and hour</h2>
              <p>
                {metric === 'occupancy'
                  ? "Each square is one zone's hourly reading. Color shows capacity use; select one for the headcount."
                  : 'Compare zone crossings by hour. Counts are not unique visitors.'}
              </p>
            </div>
            <div className="trends-metric-switch" role="group" aria-label="Heatmap measure">
              {METRICS.map((item) => (
                <button
                  type="button"
                  key={item.id}
                  aria-pressed={metric === item.id}
                  onClick={() => setMetric(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          </div>
          <ZoneHeatmap
            zones={zones}
            trends={trends}
            trafficByZone={trafficByZone}
            metric={metric}
            selectedZoneId={selectedZone?.id}
            selectedHour={selectedPoint?.hour}
            onSelect={selectCell}
          />
        </section>

        <section className="card trends-detail-card" aria-labelledby="trends-detail-title">
          <p className="trends-detail-label">Selected zone</p>
          <h2 id="trends-detail-title">{selectedZone?.name || 'No zone selected'}</h2>
          <p className="trends-selected-time">
            {selectedPoint ? formatHour(selectedPoint.hour) : 'No hourly data'}
          </p>

          <div className="trends-selected-value">
            <strong>{selectedValue ?? '—'}</strong>
            <span>{selectedUnit}</span>
          </div>

          {selectedStatus && (
            <>
              <div className={`trends-status-pill trends-status-${selectedStatus.key}`}>
                {selectedStatus.label} · {Math.round(selectedStatus.pct)}% of capacity
              </div>
              <div
                className="trends-capacity-meter"
                role="meter"
                aria-label={`${selectedZone.name} capacity use`}
                aria-valuemin={0}
                aria-valuemax={selectedZone.capacity}
                aria-valuenow={selectedValue}
              >
                <span
                  className={`trends-capacity-fill trends-capacity-fill-${selectedStatus.key}`}
                  style={{ width: `${Math.min(selectedStatus.pct, 100)}%` }}
                />
              </div>
            </>
          )}

          <dl className="trends-zone-facts">
            <div>
              <dt>Peak occupancy</dt>
              <dd>
                {selectedPeak
                  ? `${selectedPeak.point.occupancy} of ${selectedZone.capacity}`
                  : '—'}
              </dd>
            </div>
            <div>
              <dt>Peak hour</dt>
              <dd>{selectedPeak ? formatHour(selectedPeak.point.hour) : '—'}</dd>
            </div>
          </dl>

          <p className="trends-detail-note">
            {metric === 'occupancy'
              ? 'Select a square for its headcount. A hatched square means no reading, not an empty zone.'
              : 'Zone crossings can count the same person in multiple zones.'}
          </p>
        </section>
      </div>
    </div>
  );
}
