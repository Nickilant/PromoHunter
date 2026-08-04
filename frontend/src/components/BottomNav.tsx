import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';

import Icon from './Icon';
import type { IconName } from './Icon';

// Плавающий док: сетка из равных колонок (не выезжает на узких экранах),
// подсветка активного пункта плавно переезжает между кнопками.
interface NavItem {
  to: string;
  icon: IconName;
  label: string;
  slot: number;
  match: (pathname: string) => boolean;
}

const NAV: NavItem[] = [
  {
    to: '/promotions',
    icon: 'tag',
    label: 'Акции',
    slot: 0,
    match: (p) => p === '/promotions' || p.startsWith('/brand'),
  },
  { to: '/map', icon: 'map', label: 'Карта', slot: 1, match: (p) => p === '/map' },
  { to: '/rating', icon: 'trophy', label: 'Рейтинг', slot: 3, match: (p) => p === '/rating' },
  { to: '/profile', icon: 'user', label: 'Профиль', slot: 4, match: (p) => p === '/profile' },
];

export default function BottomNav() {
  const { pathname } = useLocation();
  const active = NAV.find((item) => item.match(pathname));
  const slot = active?.slot ?? -1;

  // Подсветка едет сразу по нажатию, не дожидаясь монтирования новой
  // страницы (карта с Leaflet тяжёлая — иначе плашка трогается с задержкой)
  const [pressed, setPressed] = useState<number | null>(null);
  useEffect(() => setPressed(null), [pathname]);

  // Последний валидный слот: на страницах вне дока (/suggest, /login)
  // плашка гаснет на месте, а не уезжает в первую колонку
  const lastSlot = useRef(0);
  if (slot >= 0) lastSlot.current = slot;
  const shown = pressed ?? (slot >= 0 ? slot : lastSlot.current);
  const hasVisibleIndicator = slot >= 0 || pressed !== null;

  const indicator = useRef<HTMLSpanElement>(null);

  // При первом рендере плашка просто стоит на месте, а не приезжает слева
  useEffect(() => {
    const el = indicator.current;
    if (!el) return;
    const id = requestAnimationFrame(() => el.classList.add('animated'));
    return () => cancelAnimationFrame(id);
  }, []);

  const renderItem = (item: NavItem) => {
    const isActive = active?.to === item.to;
    // На центральной вкладке индикатор скрыт — обычные пункты не должны
    // сохранять его зелёный цвет только из-за запомненной позиции.
    const isTarget = hasVisibleIndicator && shown === item.slot;
    return (
      <Link
        key={item.to}
        to={item.to}
        className={`dock-item ${isActive ? 'active' : ''} ${isTarget ? 'lit' : ''}`}
        aria-current={isActive ? 'page' : undefined}
        // click подтверждает полноценный тап. pointerdown/pointerleave в
        // мобильных WebView могут приходить подряд и дёргать индикатор назад.
        onClick={() => setPressed(item.slot)}
      >
        <Icon name={item.icon} size={22} />
        <span>{item.label}</span>
      </Link>
    );
  };

  return (
    <nav className="dock" aria-label="Основная навигация">
      <span
        ref={indicator}
        className="dock-indicator"
        style={{
          opacity: hasVisibleIndicator ? 1 : 0,
          transform: `translateX(${shown * 100}%)`,
        }}
      />
      {NAV.slice(0, 2).map(renderItem)}
      {/* Центральная кнопка — «что рядом»: это то, зачем сервис открывают
          чаще всего. Заявки переехали в профиль, они нужны реже */}
      <Link
        to="/nearby"
        className={`dock-action${pathname.startsWith('/nearby') ? ' active' : ''}`}
        aria-label="Точки рядом со мной"
        aria-current={pathname.startsWith('/nearby') ? 'page' : undefined}
        onClick={() => setPressed(null)}
      >
        <Icon name="locate" size={24} strokeWidth={2} />
      </Link>
      {NAV.slice(2).map(renderItem)}
    </nav>
  );
}
