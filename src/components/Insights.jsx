import React from 'react';
import { Lightbulb } from 'lucide-react';

export default function Insights({ items }) {
  return (
    <div className="card">
      <h2>Insights</h2>
      <ul className="insights">
        {items.map((i) => (
          <li key={i.id}><Lightbulb size={16} aria-hidden /> <span>{i.text}</span></li>
        ))}
      </ul>
    </div>
  );
}
