import React, { useEffect, useState } from 'react';
import StoreKpis from '../components/StoreKpis';
import Recommendations from '../components/Recommendations';
import BusyHeatmap from '../components/BusyHeatmap';
import { VisitorsByWeekday, VisitorsByHour, DailyVisitors } from '../components/VisitorCharts';
import { ZoneSharePie, DwellPie, ZoneScorecard } from '../components/ZoneCharts';
import AlertsList from '../components/AlertsList';
import { useSites, useStoreAnalytics } from '../hooks/useStoreAnalytics';

const RANGES = [7, 28, 42];

// Store insights: what weeks of counts tell a store manager, and what to do about it.
export default function StorePage() {
  const { data: sites } = useSites();
  const [siteId, setSiteId] = useState(null);
  const [days, setDays] = useState(28);
  // Start on the sample store when there is one; it has weeks of history to show.
  useEffect(() => {
    if (!siteId && sites?.length) setSiteId((sites.find((s) => s.kind === 'sample') || sites[0]).id);
  }, [sites, siteId]);
  const { data: a, error } = useStoreAnalytics(siteId, days);
  const site = sites?.find((s) => s.id === siteId);

  return (
    <>
      <div className="page-head store-head">
        <h1>Store insights</h1>
        <div className="controls">
          {sites?.length > 1 && (
            <label className="select">
              <span className="sr-only">Store</span>
              <select value={siteId || ''} onChange={(e) => setSiteId(e.target.value)}>
                {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
          )}
          <div className="segmented" role="group" aria-label="Period">
            {RANGES.map((d) => (
              <button key={d} type="button" className={d === days ? 'on' : ''} aria-pressed={d === days} onClick={() => setDays(d)}>
                {d === 7 ? '7 days' : `${d / 7} weeks`}
              </button>
            ))}
          </div>
        </div>
      </div>
      {site?.kind === 'sample' && (
        <p className="sample-note">
          Sample data: a simulated neighborhood market, generated with <code>npm run mock-store</code> to show what weeks
          of camera counts look like. It goes through the same database and API as the live camera.
        </p>
      )}
      {!a ? (
        <div className="card"><p className="kpi-sub">{error ? `Can't load analytics: ${error.message}` : 'Loading…'}</p></div>
      ) : (
        <>
          <StoreKpis kpis={a.kpis} days={a.range.days} />
          <Recommendations items={a.recommendations} />
          <div className="grid-2 store-grid">
            <BusyHeatmap rows={a.heatmap} />
            <ZoneSharePie share={a.zoneShare} zones={a.zones} />
          </div>
          <div className="grid-even">
            <VisitorsByWeekday data={a.byWeekday} />
            <VisitorsByHour data={a.byHour} />
          </div>
          <div className="grid-2 store-grid">
            <DailyVisitors data={a.daily} />
            <DwellPie buckets={a.dwellBuckets} />
          </div>
          <div className="grid-2 store-grid">
            <ZoneScorecard zones={a.zones} />
            <AlertsList alerts={a.alerts} />
          </div>
        </>
      )}
    </>
  );
}
