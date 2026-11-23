import React from 'react';
import { THRESHOLDS, getStatus } from '../utils/status';

export default function SeatStrip({ count, capacity, size = 'lg' }) {
  const { key } = getStatus(count, capacity);
  const value = Math.max(0, Math.min(capacity, count));
  const percentage = capacity > 0 ? (value / capacity) * 100 : 0;
  const tickCount = Math.min(capacity, 24);
  const filledTicks = Math.round((percentage / 100) * tickCount);

  if (size === 'lg') {
    return (
      <div
        className={`occupancy-meter status-${key}`}
        role="meter"
        aria-label="Current occupancy"
        aria-valuemin={0}
        aria-valuemax={capacity}
        aria-valuenow={value}
        aria-valuetext={`${value} of ${capacity} spots occupied`}
      >
        <div className="occupancy-track">
          <div className="occupancy-fill" style={{ width: `${percentage}%` }} />
        </div>
        <span className="seats-mark" style={{ left: `${THRESHOLDS.moderate}%` }} />
        <span className="seats-mark" style={{ left: `${THRESHOLDS.busy}%` }} />
      </div>
    );
  }

  return (
    <div
      className={`seats seats-${size} status-${key}`}
      role="meter"
      aria-label="Zone occupancy"
      aria-valuemin={0}
      aria-valuemax={capacity}
      aria-valuenow={value}
      aria-valuetext={`${value} of ${capacity} spots occupied`}
    >
      <div className="seats-ticks">
        {Array.from({ length: tickCount }, (_, i) => (
          <span key={i} className={i < filledTicks ? 'seat on' : 'seat'} />
        ))}
      </div>
      <span className="seats-mark" style={{ left: `${THRESHOLDS.moderate}%` }} />
      <span className="seats-mark" style={{ left: `${THRESHOLDS.busy}%` }} />
    </div>
  );
}
