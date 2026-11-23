import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import TrendsPage from './TrendsPage';

test('ranks the three zones by peak capacity percentage and shows their peak details', () => {
  const zones = [
    { id: 'bookstore', name: 'Bookstore', capacity: 100 },
    { id: 'grill', name: 'Grill Queue', capacity: 10 },
    { id: 'lounge', name: 'Student Lounge', capacity: 20 },
    { id: 'cards', name: 'Card Services', capacity: 50 },
  ];
  const trends = {
    bookstore: [{ hour: 14, occupancy: 80 }],
    grill: [{ hour: 12, occupancy: 9 }],
    lounge: [{ hour: 10, occupancy: 15 }],
    cards: [{ hour: 16, occupancy: 40 }],
  };

  const markup = renderToStaticMarkup(<TrendsPage zones={zones} trends={trends} />);
  const ranking = markup.match(
    /<ol class="trends-pressure-list" aria-label="Top zones by peak occupancy">([\s\S]*?)<\/ol>/
  )?.[1];

  expect(ranking).toBeTruthy();
  expect(ranking.match(/<li\b/g)).toHaveLength(3);
  expect(ranking.indexOf('Grill Queue')).toBeLessThan(ranking.indexOf('Bookstore'));
  expect(ranking.indexOf('Bookstore')).toBeLessThan(ranking.indexOf('Card Services'));
  expect(ranking).toContain('90%');
  expect(ranking).toContain('9 of 10 people at 12:00 PM');
  expect(ranking).not.toContain('Student Lounge');
});

test('shows an empty state when no zone has occupancy history', () => {
  const markup = renderToStaticMarkup(
    <TrendsPage
      zones={[{ id: 'lounge', name: 'Student Lounge', capacity: 20 }]}
      trends={{ lounge: [{ hour: 10, occupancy: null }] }}
    />
  );

  expect(markup).toContain('No occupancy readings for this period.');
});
