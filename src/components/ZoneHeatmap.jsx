import React from 'react';
import { getStatus } from '../utils/status';

const METRICS = {
  occupancy: 'occupancy',
  entries: 'entries',
  exits: 'exits',
};

function formatHour(hour) {
  const value = Number(hour);
  return `${value % 12 || 12} ${value < 12 ? 'AM' : 'PM'}`;
}

function metricValue(zoneId, point, metric, trends, trafficByZone) {
  if (metric === METRICS.occupancy) {
    return (trends[zoneId] || []).find((item) => item.hour === point.hour)?.occupancy ?? null;
  }
  return (trafficByZone[zoneId] || []).find((item) => item.hour === point.hour)?.[metric] ?? null;
}

function cellDescription(zone, point, metric, value) {
  const time = formatHour(point.hour);
  if (value == null) return `${zone.name}, ${time}: no ${metric} reading`;
  if (metric !== METRICS.occupancy) {
    const unit = metric === METRICS.entries
      ? value === 1 ? 'entry' : 'entries'
      : value === 1 ? 'exit' : 'exits';
    return `${zone.name}, ${time}: ${value} ${unit} (zone crossings)`;
  }
  const status = getStatus(value, zone.capacity);
  return `${zone.name}, ${time}: ${value} people, ${Math.round(status.pct)}% of capacity, ${status.label}`;
}

export default function ZoneHeatmap({
  zones = [],
  trends = {},
  trafficByZone = {},
  metric = METRICS.occupancy,
  selectedZoneId,
  selectedHour,
  onSelect,
}) {
  const hours = zones.length ? trends[zones[0].id] || [] : [];
  const values = zones.flatMap((zone) =>
    (trafficByZone[zone.id] || [])
      .map((point) => point[metric])
      .filter((value) => value != null)
  );
  const maxFlow = Math.max(0, ...values);
  const hasData = zones.some((zone) =>
    hours.some((point) => metricValue(zone.id, point, metric, trends, trafficByZone) != null)
  );
  return (
    <div className="trends-heatmap-wrap">
      <div className="trends-heatmap-scroll" role="region" aria-label="Hourly zone heatmap" tabIndex={0}>
        <table className="trends-heatmap">
          <thead>
            <tr>
              <th scope="col">Zone</th>
              {hours.map((point, index) => (
                <th scope="col" key={point.hour} aria-label={formatHour(point.hour)}>
                  {index % 4 === 0 && (
                    <span className="trends-time-label">{formatHour(point.hour)}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {zones.map((zone) => (
              <tr key={zone.id}>
                <th scope="row">
                  <button
                    className="trends-zone-select"
                    type="button"
                    aria-pressed={selectedZoneId === zone.id}
                    onClick={() => onSelect(zone.id, selectedHour)}
                  >
                    <span>{zone.name}</span>
                    <small>Capacity {zone.capacity}</small>
                  </button>
                </th>
                {hours.map((hour) => {
                  const value = metricValue(zone.id, hour, metric, trends, trafficByZone);
                  const status = metric === METRICS.occupancy && value != null
                    ? getStatus(value, zone.capacity)
                    : null;
                  const opacity = metric === METRICS.occupancy
                    ? 0.18 + (Math.min(status?.pct ?? 0, 100) / 100) * 0.82
                    : 0.18 + (maxFlow > 0 ? (value / maxFlow) * 0.82 : 0);
                  const description = cellDescription(zone, hour, metric, value);

                  return (
                    <td key={hour.hour}>
                      <button
                        className={[
                          'trends-heat-cell',
                          status ? `trends-heat-${status.key}` : '',
                          metric !== METRICS.occupancy ? 'trends-heat-flow' : '',
                          value == null ? 'trends-heat-missing' : '',
                          selectedZoneId === zone.id && selectedHour === hour.hour ? 'is-selected' : '',
                        ].filter(Boolean).join(' ')}
                        type="button"
                        aria-label={description}
                        aria-pressed={selectedZoneId === zone.id && selectedHour === hour.hour}
                        title={description}
                        style={value == null ? undefined : { opacity }}
                        onClick={() => onSelect(zone.id, hour.hour)}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {metric === METRICS.occupancy ? (
        <ul className="trends-legend" aria-label="Occupancy heatmap legend">
          <li><span className="trends-legend-swatch trends-heat-available" />Available under 50%</li>
          <li><span className="trends-legend-swatch trends-heat-moderate" />Moderate 50-75%</li>
          <li><span className="trends-legend-swatch trends-heat-busy" />Busy over 75%</li>
          <li><span className="trends-legend-swatch trends-heat-missing" />No reading</li>
        </ul>
      ) : (
        <ul className="trends-legend" aria-label="Crossing heatmap legend">
          <li><span className="trends-legend-swatch trends-legend-flow-low" />Fewer crossings</li>
          <li><span className="trends-legend-swatch trends-legend-flow-high" />More crossings</li>
          <li><span className="trends-legend-swatch trends-heat-missing" />No reading</li>
        </ul>
      )}
      {!hasData && (
        <p className="trends-data-note">
          {metric === METRICS.occupancy
            ? 'No occupancy readings for this period.'
            : 'No crossing readings for this period. Line-crossing detection may be off.'}
        </p>
      )}
    </div>
  );
}
