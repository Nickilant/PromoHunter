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
    to: '/',
    icon: 'tag',
    label: 'Акции',
    slot: 0,
    match: (p) => p === '/' || p.startsWith('/brand'),
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

  const indicator = useRef<HTMLSpanElement>(null);

  // При первом рендере плашка просто стоит на месте, а не приезжает слева
  useEffect(() => {
    const el = indicator.current;
    if (!el) return;
    const id = requestAnimationFrame(() => el.classList.add('animated'));
    return () => cancelAnimationFrame(id);
  }, []);

  // Указатель увели с кнопки — перехода не будет, подсветку возвращаем на
  // место. Иначе после «нажал и провёл пальцем мимо» плашка оставалась на
  // кнопке, хотя вкладка не переключилась.
  const cancelPress = () => setPressed(null);

  const renderItem = (item: NavItem) => {
    const isActive = active?.to === item.to;
    const isTarget = shown === item.slot;
    return (
      <Link
        key={item.to}
        to={item.to}
        className={`dock-item ${isActive ? 'active' : ''} ${isTarget ? 'lit' : ''}`}
        aria-current={isActive ? 'page' : undefined}
        onPointerDown={(e) => {
          // Тач по умолчанию захватывает указатель целью, и pointerleave до
          // неё не доходит — снимаем захват, иначе отмену не поймать
          if (e.currentTarget.hasPointerCapture?.(e.pointerId)) {
            e.currentTarget.releasePointerCapture(e.pointerId);
          }
          setPressed(item.slot);
        }}
        onPointerLeave={cancelPress}
        onPointerCancel={cancelPress}
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
          opacity: slot < 0 && pressed === null ? 0 : 1,
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
        onPointerDown={() => setPressed(null)}
      >
        <Icon name="plus" size={24} strokeWidth={2.2} />
      </Link>
      {NAV.slice(2).map(renderItem)}
    </nav>
  );
}
