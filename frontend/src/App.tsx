import { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';

import AdminLayout from './admin/AdminLayout';
import AdminBrands from './admin/AdminBrands';
import AdminPromotions from './admin/AdminPromotions';
import AdminRestaurants from './admin/AdminRestaurants';
import AdminRestaurantSuggestions from './admin/AdminRestaurantSuggestions';
import AdminSuggestions from './admin/AdminSuggestions';
import AdminUsers from './admin/AdminUsers';
import BottomNav from './components/BottomNav';
import TelegramGate from './components/TelegramGate';
import { useAuth } from './hooks/useAuth';
import BrandPage from './pages/BrandPage';
import FeedPage from './pages/FeedPage';
import LoginPage from './pages/LoginPage';
import MapPage from './pages/MapPage';
import ProfilePage from './pages/ProfilePage';
import RatingPage from './pages/RatingPage';
import RegisterPage from './pages/RegisterPage';
import SuggestHubPage from './pages/SuggestHubPage';
import SuggestPage from './pages/SuggestPage';
import SuggestRestaurantPage from './pages/SuggestRestaurantPage';

function UserShell() {
  const { pathname } = useLocation();
  // Карта занимает весь экран сама — отступ под док создавал бы
  // «резиновую» прокрутку поверх неё
  const fullBleed = pathname === '/map';
  return (
    <div className={`app-shell${fullBleed ? ' full-bleed' : ''}`}>
      <Outlet />
      <BottomNav />
    </div>
  );
}

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

function RequireAdmin({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user || user.role !== 'admin') return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <>
      <TelegramGate />
      <Routes>
      <Route element={<UserShell />}>
        <Route path="/" element={<FeedPage />} />
        <Route path="/brand/:brandId" element={<BrandPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/rating" element={<RatingPage />} />
        <Route
          path="/suggest"
          element={
            <RequireAuth>
              <SuggestHubPage />
            </RequireAuth>
          }
        />
        <Route
          path="/suggest/promotion"
          element={
            <RequireAuth>
              <SuggestPage />
            </RequireAuth>
          }
        />
        <Route
          path="/suggest/restaurant"
          element={
            <RequireAuth>
              <SuggestRestaurantPage />
            </RequireAuth>
          }
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <ProfilePage />
            </RequireAuth>
          }
        />
      </Route>

      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      <Route
        path="/admin"
        element={
          <RequireAdmin>
            <AdminLayout />
          </RequireAdmin>
        }
      >
        <Route index element={<Navigate to="brands" replace />} />
        <Route path="brands" element={<AdminBrands />} />
        <Route path="restaurants" element={<AdminRestaurants />} />
        <Route path="promotions" element={<AdminPromotions />} />
        <Route path="users" element={<AdminUsers />} />
        <Route path="suggestions" element={<AdminSuggestions />} />
        <Route path="restaurant-suggestions" element={<AdminRestaurantSuggestions />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}
