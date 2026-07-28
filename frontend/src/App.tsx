import { ReactNode } from 'react';
import { Navigate, Outlet, Route, Routes } from 'react-router-dom';

import AdminLayout from './admin/AdminLayout';
import AdminBrands from './admin/AdminBrands';
import AdminPromotions from './admin/AdminPromotions';
import AdminRestaurants from './admin/AdminRestaurants';
import AdminSuggestions from './admin/AdminSuggestions';
import AdminUsers from './admin/AdminUsers';
import BottomNav from './components/BottomNav';
import { useAuth } from './hooks/useAuth';
import BrandPage from './pages/BrandPage';
import FeedPage from './pages/FeedPage';
import LoginPage from './pages/LoginPage';
import MapPage from './pages/MapPage';
import ProfilePage from './pages/ProfilePage';
import RatingPage from './pages/RatingPage';
import RegisterPage from './pages/RegisterPage';
import SuggestPage from './pages/SuggestPage';

function UserShell() {
  return (
    <div className="app-shell">
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
              <SuggestPage />
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
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
