import { useCallback, useEffect, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';

import { api } from '../api/client';
import type { SuggestionGroup } from '../types';

export interface AdminOutletContext {
  refreshPendingCount: () => void;
}

const links = [
  { to: 'brands', label: 'Бренды' },
  { to: 'restaurants', label: 'Рестораны' },
  { to: 'promotions', label: 'Акции' },
  { to: 'users', label: 'Пользователи' },
  { to: 'suggestions', label: 'Заявки' },
];

export default function AdminLayout() {
  const [pending, setPending] = useState(0);

  const refreshPendingCount = useCallback(() => {
    api
      .get<SuggestionGroup[]>('/admin/suggestions?status=pending')
      .then((groups) =>
        setPending(groups.reduce((sum, g) => sum + g.suggestions.length, 0)),
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshPendingCount();
  }, [refreshPendingCount]);

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="brand-title">PromoHunter · Админка</div>
        {links.map((l) => (
          <NavLink
            key={l.to}
            to={l.to}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <span>{l.label}</span>
            {l.to === 'suggestions' && pending > 0 && (
              <span className="counter">{pending}</span>
            )}
          </NavLink>
        ))}
        <div className="spacer" />
        <Link to="/">← В приложение</Link>
      </aside>
      <main className="admin-content">
        <Outlet context={{ refreshPendingCount } satisfies AdminOutletContext} />
      </main>
    </div>
  );
}
