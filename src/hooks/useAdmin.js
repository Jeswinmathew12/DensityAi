import { useEffect, useState } from 'react';
import { fetchAdminCameras, fetchPreviewFrame } from '../services/api';

const KEY = 'densityai-admin';
// Kept for this browser tab only, so closing the tab logs out.
const readSaved = () => {
  try { return sessionStorage.getItem(KEY) || ''; } catch { return ''; }
};
const save = (pw) => {
  try { pw ? sessionStorage.setItem(KEY, pw) : sessionStorage.removeItem(KEY); } catch { /* private mode */ }
};

const errorText = (err) => {
  if (err.status === 401) return 'Wrong password.';
  if (err.status === 404) return 'Admin is off on the Jetson. Set ADMIN_PASSWORD in /etc/densityai.env and restart the service.';
  return "Can't reach the backend.";
};

// Admin login plus the camera list (refreshed every 5 s, so a preview appears when the pipeline starts).
export function useAdmin() {
  const [password, setPassword] = useState(readSaved);
  const [cameras, setCameras] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!password) return undefined;
    let cancelled = false;
    const load = () => fetchAdminCameras(password).then(
      (list) => { if (!cancelled) { setCameras(list); setError(''); } },
      (err) => {
        if (cancelled) return;
        setError(errorText(err));
        if (err.status === 401 || err.status === 404) { save(''); setPassword(''); }
      },
    );
    load();
    const id = setInterval(load, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [password]);

  const login = (pw) => { setError(''); save(pw); setPassword(pw); };
  const logout = () => { save(''); setPassword(''); setCameras(null); };
  return { password, cameras, error, login, logout };
}

// Polls one camera's preview about twice a second. Returns an object URL for an <img>, or null.
export function useCameraPreview(cameraId, password, enabled) {
  const [src, setSrc] = useState(null);

  useEffect(() => {
    if (!enabled) { setSrc(null); return undefined; }
    let cancelled = false;
    let timer;
    let url = null;
    const tick = async () => {
      try {
        const blob = await fetchPreviewFrame(cameraId, password);
        if (cancelled) return;
        const next = URL.createObjectURL(blob);
        setSrc(next);
        if (url) URL.revokeObjectURL(url);
        url = next;
      } catch {
        if (!cancelled) setSrc(null);
      }
      if (!cancelled) timer = setTimeout(tick, 500);
    };
    tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (url) URL.revokeObjectURL(url);
    };
  }, [cameraId, password, enabled]);

  return src;
}
