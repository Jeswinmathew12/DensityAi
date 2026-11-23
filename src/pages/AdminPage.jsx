import React, { useState } from 'react';
import { CameraOff } from 'lucide-react';
import { useAdmin, useCameraPreview } from '../hooks/useAdmin';

function CameraPreview({ camera, zoneName, password }) {
  const src = useCameraPreview(camera.id, password, camera.preview);
  return (
    <div className="card">
      <h2>{camera.id} <span className="kpi-sub">· {zoneName}</span></h2>
      {src ? (
        <img className="preview" src={src} alt={`Live view from ${camera.id} with detected people boxed`} />
      ) : (
        <div className="preview preview-empty">
          <CameraOff size={28} aria-hidden />
          <p>No live view. The camera pipeline is not running, or it started before ADMIN_PASSWORD was set.</p>
        </div>
      )}
    </div>
  );
}

function LoginForm({ onLogin, error }) {
  const [value, setValue] = useState('');
  const submit = (e) => {
    e.preventDefault();
    if (value) onLogin(value);
  };
  return (
    <form className="card admin-login" onSubmit={submit}>
      <h2>Admin login</h2>
      <p className="kpi-sub">The camera view is for admins only. Everyone else sees counts, never video.</p>
      <label htmlFor="admin-password">Password</label>
      <div className="admin-row">
        <input id="admin-password" type="password" autoComplete="current-password"
          value={value} onChange={(e) => setValue(e.target.value)} />
        <button type="submit" className="btn">Unlock</button>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  );
}

// Live camera view with PeopleNet's boxes and the counting zone drawn on it.
// Frames stay on the Jetson; this page only shows them to someone with the admin password.
export default function AdminPage({ zones }) {
  const { password, cameras, error, login, logout } = useAdmin();
  const zoneName = (id) => (zones.find((z) => z.id === id) || {}).name || id;

  return (
    <>
      <div className="page-head">
        <h1>Admin</h1>
        {password && <button type="button" className="btn btn-quiet" onClick={logout}>Lock</button>}
      </div>
      {!password ? (
        <LoginForm onLogin={login} error={error} />
      ) : (
        <div className="stack">
          {error && <p className="form-error" role="alert">{error}</p>}
          <p className="kpi-sub">
            Live view, about 2 frames a second. Boxes are people PeopleNet found; the outline is the
            counting zone. Frames are never saved.
          </p>
          {cameras === null ? (
            <p className="kpi-sub">Loading cameras…</p>
          ) : (
            cameras.map((c) => (
              <CameraPreview key={c.id} camera={c} zoneName={zoneName(c.zoneId)} password={password} />
            ))
          )}
        </div>
      )}
    </>
  );
}
