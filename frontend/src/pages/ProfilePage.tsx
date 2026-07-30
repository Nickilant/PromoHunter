import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import GameSettings from '../components/GameSettings';
import { useAuth } from '../hooks/useAuth';
import { useSubscriptions } from '../hooks/useSubscriptions';
import type { Report, RestaurantSuggestion, Suggestion, TelegramInfo } from '../types';
import { formatDateTime } from '../utils/time';
import Icon from '../components/Icon';

const SUGGESTION_LABELS: Record<Suggestion['status'], { text: string; cls: string }> = {
  pending: { text: 'На модерации', cls: 'warn' },
  approved: { text: 'Одобрена', cls: 'ok' },
  rejected: { text: 'Отклонена', cls: 'error' },
};

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [reports, setReports] = useState<Report[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [restSuggestions, setRestSuggestions] = useState<RestaurantSuggestion[]>([]);
  const [tgInfo, setTgInfo] = useState<TelegramInfo | null>(null);
  const { subscriptions, remove } = useSubscriptions();
  const navigate = useNavigate();

  useEffect(() => {
    if (!user) return;
    api.get<Report[]>('/reports/mine?limit=100').then(setReports).catch(() => {});
    api.get<Suggestion[]>('/suggestions/mine').then(setSuggestions).catch(() => {});
    api
      .get<RestaurantSuggestion[]>('/restaurant-suggestions/mine')
      .then(setRestSuggestions)
      .catch(() => {});
    if (!user.is_phone_verified) {
      api.get<TelegramInfo>('/telegram/info').then(setTgInfo).catch(() => {});
    }
  }, [user]);

  if (!user) return null;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Профиль</h1>
        <Link to="/suggest" className="btn btn-accent btn-small">
          <Icon name="plus" size={16} strokeWidth={2.2} />
          Заявить акцию
        </Link>
      </div>

      <div className="profile-card">
        <div className="row">
          <span className="muted">Имя</span>
          <span>{user.display_name}</span>
        </div>
        <div className="row">
          <span className="muted">Телефон</span>
          <span>
            {user.phone}{' '}
            {user.is_phone_verified ? (
              <span className="tag ok">подтверждён</span>
            ) : (
              <span className="tag warn">не подтверждён</span>
            )}
          </span>
        </div>
        <div className="row">
          <span className="muted">Город</span>
          <span>{user.city ?? '—'}</span>
        </div>
        {!user.is_phone_verified && (
          <div className="verify-block">
            Подтвердите номер через Telegram-бота: нажмите Start и кнопку
            «📱 Подтвердить номер» — подтверждённым отчётам больше доверия,
            а бот сможет присылать уведомления по подпискам.
            {tgInfo?.bot_username && (
              <a
                className="btn btn-primary btn-block"
                style={{ marginTop: 8 }}
                href={`https://t.me/${tgInfo.bot_username}`}
                target="_blank"
                rel="noreferrer"
              >
                Открыть бота
              </a>
            )}
          </div>
        )}
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
          <Icon name="logout" size={17} />
          Выйти
        </button>
      </div>

      <GameSettings />

      <div className="section-title">Мои подписки</div>
      {!user.has_telegram && (
        <div className="list-item muted">
          Подписки работают через Telegram-бота — откройте сервис из Telegram,
          чтобы получать уведомления о новых акциях и статусах
        </div>
      )}
      {user.has_telegram && subscriptions.length === 0 && (
        <div className="list-item muted">
          Подписок пока нет — включите колокольчик у акции или точки
        </div>
      )}
      {subscriptions.map((s) => (
        <div className="list-item" key={s.id}>
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
            <span>
              <span className="sub-item">
                <Icon name={s.restaurant ? 'pin' : 'tag'} size={16} />
                {s.restaurant
                  ? `${s.restaurant.title || s.restaurant.brand.name}, ${s.restaurant.address}`
                  : `${s.promotion?.title} (${s.promotion?.brand.name})`}
              </span>
            </span>
            <button className="btn btn-ghost btn-small" onClick={() => remove(s.id)}>
              Отписаться
            </button>
          </div>
        </div>
      ))}

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
                <Icon
                  name={i.is_available ? 'checkCircle' : 'crossCircle'}
                  size={15}
                  className={i.is_available ? 'ico-yes' : 'ico-no'}
                />
                {i.name}
              </span>
            ))}
          </div>
          <div className="muted">{formatDateTime(r.created_at)}</div>
        </div>
      ))}

      <div className="section-title">Мои заявки на акции</div>
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

      <div className="section-title">Мои заявки на рестораны</div>
      {restSuggestions.length === 0 && (
        <div className="list-item muted">Заявок пока нет</div>
      )}
      {restSuggestions.map((s) => {
        const label = SUGGESTION_LABELS[s.status];
        return (
          <div className="list-item" key={s.id}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
              <strong>
                {s.brand.name} — {s.city}, {s.address}
              </strong>
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
