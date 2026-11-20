import React from 'react';
import { Camera, Server, Database, Globe, MonitorSmartphone, ArrowRight } from 'lucide-react';

const ago = (epoch) => {
  if (!epoch) return 'never';
  const s = Math.max(0, Math.round(Date.now() / 1000 - epoch));
  return s < 60 ? `${s} s ago` : `${Math.round(s / 60)} min ago`;
};

// Each hop from the camera to this page, left to right, with whether it's working right now.
export default function SystemFlow({ status }) {
  const cams = status.cameras;
  const camOk = cams.some((c) => !c.stale);
  const fps = cams.find((c) => c.fps)?.fps;
  const fresh = status.collector.lastEventAt && Date.now() / 1000 - status.collector.lastEventAt < 15;
  const steps = [
    {
      icon: Camera, title: 'Camera + Jetson', ok: camOk,
      lines: ['PeopleNet person detection on the edge', camOk ? `${fps ? `${fps.toFixed(0)} FPS, ` : ''}counting` : 'no counts right now', 'Sends numbers only, never video'],
    },
    {
      icon: Server, title: 'Collector', ok: fresh,
      lines: ['Receives counts, writes events', `${status.collector.eventsLastMinute} events in the last minute`, `Last event ${ago(status.collector.lastEventAt)}`],
    },
    {
      icon: Database, title: 'PostgreSQL', ok: true,
      lines: [`Database ${status.database.name}`, `${(status.database.events ?? 0).toLocaleString()} events stored`, status.database.timescale ? 'TimescaleDB time-series table' : 'Events table (time-indexed)'],
    },
    {
      icon: Globe, title: 'Web service', ok: !!status.web.lastPoll,
      lines: ['REST API + live updates', `Read the database ${ago(status.web.lastPoll)}`, `${status.web.dashboards} live dashboard${status.web.dashboards === 1 ? '' : 's'} open`],
    },
    {
      icon: MonitorSmartphone, title: 'Dashboard', ok: true,
      lines: ['Any browser on the network', 'Talks only to the web service', "You're looking at it"],
    },
  ];
  return (
    <ol className="flow">
      {steps.map((s, i) => {
        const Icon = s.icon;
        return (
          <React.Fragment key={s.title}>
            <li className={`card flow-step ${s.ok ? 'ok' : 'down'}`}>
              <div className="flow-head">
                <Icon size={20} aria-hidden />
                <span className={`badge ${s.ok ? 'status-available' : 'status-offline'}`}>{s.ok ? 'Working' : 'Idle'}</span>
              </div>
              <h2>{s.title}</h2>
              {s.lines.map((l) => <p key={l} className="kpi-sub">{l}</p>)}
            </li>
            {i < steps.length - 1 && <li className="flow-arrow" aria-hidden><ArrowRight size={18} /></li>}
          </React.Fragment>
        );
      })}
    </ol>
  );
}
