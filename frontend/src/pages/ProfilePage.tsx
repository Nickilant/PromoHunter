import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import GameSettings from '../components/GameSettings';
import Icon from '../components/Icon';
import PasswordSettings from '../components/PasswordSettings';
import ProfileSection from '../components/ProfileSection';
import { useAuth } from '../hooks/useAuth';
import { useSubscriptions } from '../hooks/useSubscriptions';
import type { Report, RestaurantSuggestion, Suggestion, TelegramInfo } from '../types';
import { DEVELOPER_TELEGRAM, DEVELOPER_TELEGRAM_URL } from '../utils/contacts';
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

  const allSuggestions = suggestions.length + restSuggestions.length;

  return (
    <div className="page">
      <div className="page-header">
        <h1>Профиль</h1>
        <Link to="/suggest" className="btn btn-accent btn-small">
          <Icon name="plus" size={16} strokeWidth={2.2} />
          Заявить акцию
        </Link>
      </div>

      {/* Кто я: имя крупно, остальное — подписью. Раньше это была таблица
          из трёх одинаковых строк, в которой имя терялось */}
      <div className="profile-id">
        <div className="profile-avatar" aria-hidden="true">
          {user.display_name.slice(0, 1).toUpperCase()}
        </div>
        <div className="profile-id-body">
          <div className="profile-name">{user.display_name}</div>
          <div className="profile-id-meta">
            {user.phone}
            {user.is_phone_verified ? (
              <span className="tag ok">подтверждён</span>
            ) : (
              <span className="tag warn">не подтверждён</span>
            )}
          </div>
          <div className="profile-id-meta muted">
            <Icon name="pin" size={14} />
            {user.city ?? 'город не выбран'}
          </div>
        </div>
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

      {/* Что я тут сделал — тремя плитками вместо строки в таблице */}
      <div className="profile-stats">
        <div className="profile-stat">
          <span className="profile-stat-value">
            {reports.length >= 100 ? '100+' : reports.length}
          </span>
          <span className="profile-stat-label">отчётов</span>
        </div>
        <div className="profile-stat">
          <span className="profile-stat-value">{allSuggestions}</span>
          <span className="profile-stat-label">заявок</span>
        </div>
        <div className="profile-stat">
          <span className="profile-stat-value">{subscriptions.length}</span>
          <span className="profile-stat-label">подписок</span>
        </div>
      </div>

      {(user.role === 'admin' || user.role === 'moderator') && (
        <Link to="/admin" className="btn btn-ghost btn-block">
          <Icon name="shield" size={17} />
          {user.role === 'moderator' ? 'Модерация моих городов' : 'Админка'}
        </Link>
      )}

      {/* «Настройки» отдельным заголовком не нужны: у пароля и игрового
          режима свои, и три заголовка подряд превращались в лесенку */}
      <PasswordSettings />
      <GameSettings />

      <div className="section-title">Моя активность</div>

      <ProfileSection title="Подписки" count={subscriptions.length}>
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
              <span className="sub-item">
                <Icon name={s.restaurant ? 'pin' : 'tag'} size={16} />
                {s.restaurant
                  ? `${s.restaurant.title || s.restaurant.brand.name}, ${s.restaurant.address}`
                  : `${s.promotion?.title} (${s.promotion?.brand.name})`}
              </span>
              <button className="btn btn-ghost btn-small" onClick={() => remove(s.id)}>
                Отписаться
              </button>
            </div>
          </div>
        ))}
      </ProfileSection>

      <ProfileSection title="Отчёты" count={reports.length}>
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
        {reports.length > 10 && (
          <div className="list-item muted">Показаны последние 10</div>
        )}
      </ProfileSection>

      <ProfileSection title="Заявки" count={allSuggestions}>
        {allSuggestions === 0 && (
          <div className="list-item muted">Заявок пока нет</div>
        )}
        {suggestions.map((s) => {
          const label = SUGGESTION_LABELS[s.status];
          return (
            <div className="list-item" key={`p${s.id}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <strong>{s.title}</strong>
                <span className={`tag ${label.cls}`}>{label.text}</span>
              </div>
              {s.moderator_comment && (
                <div className="muted">Комментарий модератора: {s.moderator_comment}</div>
              )}
              <div className="muted">Акция · {formatDateTime(s.created_at)}</div>
            </div>
          );
        })}
        {restSuggestions.map((s) => {
          const label = SUGGESTION_LABELS[s.status];
          return (
            <div className="list-item" key={`r${s.id}`}>
              <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                <strong>
                  {s.brand.name} — {s.city}, {s.address}
                </strong>
                <span className={`tag ${label.cls}`}>{label.text}</span>
              </div>
              {s.moderator_comment && (
                <div className="muted">Комментарий модератора: {s.moderator_comment}</div>
              )}
              <div className="muted">Ресторан · {formatDateTime(s.created_at)}</div>
            </div>
          );
        })}
      </ProfileSection>

      <div className="section-title">О сервисе</div>
      <div className="about-card">
        <div className="muted">Разработчик:</div>
        <a
          className="btn btn-ghost"
          href={DEVELOPER_TELEGRAM_URL}
          target="_blank"
          rel="noreferrer"
        >
          <Icon name="send" size={17} />@{DEVELOPER_TELEGRAM}
        </a>
      </div>

      {/* Выход — в самом низу: раньше он стоял рядом с именем и нажимался
          случайно при попытке открыть настройки */}
      <button
        className="btn btn-ghost btn-block profile-logout"
        onClick={() => {
          logout();
          navigate('/');
        }}
      >
        <Icon name="logout" size={17} />
        Выйти
      </button>
    </div>
  );
}
