import { useCallback, useEffect, useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';

import { api } from '../api/client';
import type { RestaurantSuggestionGroup, StaffScope, SuggestionGroup } from '../types';
import Icon from '../components/Icon';
import { useStaffScope } from './useStaffScope';

export interface AdminOutletContext {
  refreshPendingCount: () => void;
  scope: StaffScope | null;
}

const links = [
  // globalOnly — раздел общий для всей страны, городскому модератору там
  // делать нечего
  { to: 'brands', label: 'Бренды', globalOnly: true },
  { to: 'restaurants', label: 'Рестораны' },
  { to: 'promotions', label: 'Акции' },
  { to: 'users', label: 'Пользователи', globalOnly: true },
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
  const scope = useStaffScope();

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
        {scope && !scope.is_global && (
          <div className="scope-badge">
            <Icon name="pin" size={14} />
            <span>
              {scope.cities.length
                ? scope.cities.join(', ')
                : 'города не назначены'}
            </span>
          </div>
        )}
        {links
          .filter((l) => !l.globalOnly || !scope || scope.is_global)
          .map((l) => (
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
        <Outlet context={{ refreshPendingCount, scope } satisfies AdminOutletContext} />
      </main>
    </div>
  );
}
