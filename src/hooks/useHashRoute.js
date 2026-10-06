import { useEffect, useState } from 'react';

const read = () => window.location.hash.replace(/^#\/?/, '') || 'dashboard';

// Minimal hash router (no react-router dependency). Back/forward buttons work.
export default function useHashRoute() {
  const [route, setRoute] = useState(read);

  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);

  return route;
}
