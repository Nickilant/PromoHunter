import { Link, useLocation } from 'react-router-dom';

// Плавающий док: сетка из равных колонок (не выезжает на узких экранах),
// подсветка активного пункта плавно переезжает между кнопками
const NAV = [
  {
    to: '/',
    icon: '🏷️',
    label: 'Акции',
    match: (p: string) => p === '/' || p.startsWith('/brand'),
    slot: 0,
  },
  { to: '/map', icon: '🗺️', label: 'Карта', match: (p: string) => p === '/map', slot: 1 },
  {
    to: '/rating',
    icon: '🏆',
    label: 'Рейтинг',
    match: (p: string) => p === '/rating',
    slot: 3,
  },
  {
    to: '/profile',
    icon: '👤',
    label: 'Профиль',
    match: (p: string) => p === '/profile',
    slot: 4,
  },
];

export default function BottomNav() {
  const { pathname } = useLocation();
  const active = NAV.find((item) => item.match(pathname));
  const slot = active?.slot ?? -1;

  return (
    <nav className="dock" aria-label="Навигация">
      <span
        className="dock-indicator"
        style={{
          opacity: slot < 0 ? 0 : 1,
          transform: `translateX(${Math.max(slot, 0) * 100}%)`,
        }}
      />
      {NAV.slice(0, 2).map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={`dock-item ${active?.to === item.to ? 'active' : ''}`}
        >
          <span className="dock-icon">{item.icon}</span>
          <span>{item.label}</span>
        </Link>
      ))}
      <Link to="/suggest" className="dock-action" aria-label="Заявить акцию или ресторан">
        ＋
      </Link>
      {NAV.slice(2).map((item) => (
        <Link
          key={item.to}
          to={item.to}
          className={`dock-item ${active?.to === item.to ? 'active' : ''}`}
        >
          <span className="dock-icon">{item.icon}</span>
          <span>{item.label}</span>
        </Link>
      ))}
    </nav>
  );
}
