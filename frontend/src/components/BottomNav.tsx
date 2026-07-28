import { NavLink } from 'react-router-dom';

const items = [
  { to: '/', icon: '🏷️', label: 'Акции' },
  { to: '/map', icon: '🗺️', label: 'Карта' },
  { to: '/profile', icon: '👤', label: 'Профиль' },
];

export default function BottomNav() {
  return (
    <nav className="bottom-nav">
      <div className="bottom-nav-inner">
        {items.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) => (isActive ? 'active' : '')}
          >
            <span className="nav-icon">{item.icon}</span>
            <span>{item.label}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
