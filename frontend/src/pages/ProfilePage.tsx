import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import type { Report, Suggestion } from '../types';
import { formatDateTime } from '../utils/time';

const SUGGESTION_LABELS: Record<Suggestion['status'], { text: string; cls: string }> = {
  pending: { text: 'На модерации', cls: 'warn' },
  approved: { text: 'Одобрена', cls: 'ok' },
  rejected: { text: 'Отклонена', cls: 'error' },
};

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [reports, setReports] = useState<Report[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) return;
    api.get<Report[]>('/reports/mine?limit=100').then(setReports).catch(() => {});
    api.get<Suggestion[]>('/suggestions/mine').then(setSuggestions).catch(() => {});
  }, [user]);

  if (!user) return null;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Профиль</h1>
        <Link to="/suggest" className="btn btn-accent btn-small">
          + Заявить акцию
        </Link>
      </div>

      <div className="profile-card">
        <div className="row">
          <span className="muted">Имя</span>
          <span>{user.display_name}</span>
        </div>
        <div className="row">
          <span className="muted">Email</span>
          <span>{user.email}</span>
        </div>
        <div className="row">
          <span className="muted">Отчётов отправлено</span>
          <span>{reports.length >= 100 ? '100+' : reports.length}</span>
        </div>
        {user.role === 'admin' && (
          <Link to="/admin" className="btn btn-ghost">
            Перейти в админку
          </Link>
        )}
        <button
          className="btn btn-ghost"
          onClick={() => {
            logout();
            navigate('/');
          }}
        >
          Выйти
        </button>
      </div>

      <div className="section-title">Мои отчёты</div>
      {reports.length === 0 && (
        <div className="list-item muted">Вы ещё не отправляли отчётов</div>
      )}
      {reports.slice(0, 10).map((r) => (
        <div className="list-item" key={r.id}>
          <div>
            <strong>{r.promotion_title}</strong> —{' '}
            {r.restaurant.title || r.restaurant.brand.name}, {r.restaurant.address}
          </div>
          <div>
            {r.items.map((i) => (
              <span key={i.promotion_item_id} style={{ marginRight: 8 }}>
                {i.is_available ? '✅' : '❌'} {i.name}
              </span>
            ))}
          </div>
          <div className="muted">{formatDateTime(r.created_at)}</div>
        </div>
      ))}

      <div className="section-title">Мои заявки</div>
      {suggestions.length === 0 && (
        <div className="list-item muted">Заявок пока нет</div>
      )}
      {suggestions.map((s) => {
        const label = SUGGESTION_LABELS[s.status];
        return (
          <div className="list-item" key={s.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>{s.title}</strong>
              <span className={`tag ${label.cls}`}>{label.text}</span>
            </div>
            {s.moderator_comment && (
              <div className="muted">Комментарий модератора: {s.moderator_comment}</div>
            )}
            <div className="muted">{formatDateTime(s.created_at)}</div>
          </div>
        );
      })}
    </div>
  );
}
