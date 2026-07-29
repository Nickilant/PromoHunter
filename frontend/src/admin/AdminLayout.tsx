import { useCallback, useEffect, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';

import { api } from '../api/client';
import type { RestaurantSuggestionGroup, SuggestionGroup } from '../types';
import Icon from '../components/Icon';

export interface AdminOutletContext {
  refreshPendingCount: () => void;
}

const links = [
  { to: 'brands', label: 'Бренды' },
  { to: 'restaurants', label: 'Рестораны' },
  { to: 'promotions', label: 'Акции' },
  { to: 'users', label: 'Пользователи' },
  { to: 'suggestions', label: 'Заявки: акции', counter: 'promo' as const },
  {
    to: 'restaurant-suggestions',
    label: 'Заявки: рестораны',
    counter: 'restaurant' as const,
  },
];

export default function AdminLayout() {
  const [pendingPromo, setPendingPromo] = useState(0);
  const [pendingRestaurant, setPendingRestaurant] = useState(0);

  const refreshPendingCount = useCallback(() => {
    api
      .get<SuggestionGroup[]>('/admin/suggestions?status=pending')
      .then((groups) =>
        setPendingPromo(groups.reduce((sum, g) => sum + g.suggestions.length, 0)),
      )
      .catch(() => {});
    api
      .get<RestaurantSuggestionGroup[]>('/admin/restaurant-suggestions?status=pending')
      .then((groups) =>
        setPendingRestaurant(
          groups.reduce((sum, g) => sum + g.suggestions.length, 0),
        ),
      )
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshPendingCount();
  }, [refreshPendingCount]);

  const counters = { promo: pendingPromo, restaurant: pendingRestaurant };

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
            {l.counter && counters[l.counter] > 0 && (
              <span className="counter">{counters[l.counter]}</span>
            )}
          </NavLink>
        ))}
        <div className="spacer" />
        <Link to="/" className="admin-back">
          <Icon name="arrowLeft" size={16} />
          В приложение
        </Link>
      </aside>
      <main className="admin-content">
        <Outlet context={{ refreshPendingCount } satisfies AdminOutletContext} />
      </main>
    </div>
  );
}
