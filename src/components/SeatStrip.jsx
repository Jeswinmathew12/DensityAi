import React from 'react';
import { THRESHOLDS, getStatus } from '../utils/status';

// One tick per unit of capacity; filled ticks = people counted. Marks show the status thresholds.
export default function SeatStrip({ count, capacity, size = 'lg' }) {
  const { key } = getStatus(count, capacity);
  const filled = Math.min(capacity, count);
  return (
    <div
      className={`seats seats-${size} status-${key}`}
      role="img"
      aria-label={`${count} of ${capacity} spots occupied`}
    >
      <div className="seats-ticks">
        {Array.from({ length: capacity }, (_, i) => (
          <span key={i} className={i < filled ? 'seat on' : 'seat'} />
        ))}
      </div>
      <span className="seats-mark" style={{ left: `${THRESHOLDS.moderate}%` }} />
      <span className="seats-mark" style={{ left: `${THRESHOLDS.busy}%` }} />
    </div>
  );
}
