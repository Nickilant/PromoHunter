import { Link, NavLink } from 'react-router-dom';

// Плавающий док: все цели — в зоне большого пальца,
// центральная кнопка — главное действие «Заявить акцию»
export default function BottomNav() {
  return (
    <nav className="dock" aria-label="Навигация">
      <NavLink to="/" end className={({ isActive }) => `dock-item ${isActive ? 'active' : ''}`}>
        <span className="dock-icon">🏷️</span>
        <span>Акции</span>
      </NavLink>
      <NavLink to="/map" className={({ isActive }) => `dock-item ${isActive ? 'active' : ''}`}>
        <span className="dock-icon">🗺️</span>
        <span>Карта</span>
      </NavLink>
      <Link to="/suggest" className="dock-action" aria-label="Заявить акцию">
        ＋
      </Link>
      <NavLink to="/profile" className={({ isActive }) => `dock-item ${isActive ? 'active' : ''}`}>
        <span className="dock-icon">👤</span>
        <span>Профиль</span>
      </NavLink>
    </nav>
  );
}
