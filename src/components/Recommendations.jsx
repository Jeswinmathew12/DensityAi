import React from 'react';
import { Users, Wrench, Megaphone, LayoutGrid, Lightbulb } from 'lucide-react';

const KIND = {
  staffing: { icon: Users, label: 'Staffing' },
  operations: { icon: Wrench, label: 'Operations' },
  marketing: { icon: Megaphone, label: 'Marketing' },
  layout: { icon: LayoutGrid, label: 'Store layout' },
};

// The decisions a manager could make from the numbers on this page.
export default function Recommendations({ items }) {
  return (
    <section className="card" aria-label="Recommended actions">
      <h2>Recommended actions</h2>
      {items.length ? (
        <div className="recs">
          {items.map((r) => {
            const k = KIND[r.kind] || { icon: Lightbulb, label: 'Insight' };
            const Icon = k.icon;
            return (
              <article className={`rec rec-${r.kind}`} key={r.id}>
                <p className="rec-kind"><Icon size={15} aria-hidden /> {k.label}</p>
                <h3>{r.title}</h3>
                <p>{r.text}</p>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="kpi-sub">Recommendations appear once there are a few days of data.</p>
      )}
    </section>
  );
}
