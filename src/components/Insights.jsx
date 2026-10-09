import React from 'react';
import { Lightbulb } from 'lucide-react';

export default function Insights({ items }) {
  return (
    <div className="card">
      <h2>Insights</h2>
      {items.length ? (
        <ul className="insights">
          {items.map((i) => (
            <li key={i.id}><Lightbulb size={16} aria-hidden /> <span>{i.text}</span></li>
          ))}
        </ul>
      ) : (
        <p className="kpi-sub">No insights yet. They appear after about an hour of camera data.</p>
      )}
    </div>
  );
}
