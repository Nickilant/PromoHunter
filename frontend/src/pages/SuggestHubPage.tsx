import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../api/client';
import Icon from '../components/Icon';
import { useAuth } from '../hooks/useAuth';
import type { RestaurantSuggestion, Suggestion } from '../types';

// Хаб «＋»: что хочет добавить пользователь
export default function SuggestHubPage() {
  const { user } = useAuth();
  const [pending, setPending] = useState<number | null>(null);

  // Свои заявки на модерации — единственное, что человеку тут ещё интересно
  useEffect(() => {
    if (!user) {
      setPending(null);
      return;
    }
    Promise.all([
      api.get<Suggestion[]>('/suggestions/mine').catch(() => []),
      api.get<RestaurantSuggestion[]>('/restaurant-suggestions/mine').catch(() => []),
    ]).then(([promos, restaurants]) =>
      setPending(
        [...promos, ...restaurants].filter((s) => s.status === 'pending').length,
      ),
    );
  }, [user]);

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Чего-то не хватает?</h1>
        <p className="muted">
          Сервис наполняют сами посетители. Расскажите про акцию или точку —
          модератор проверит и добавит для всех.
        </p>
      </div>

      <div className="suggest-hub">
        <Link to="/suggest/promotion" className="suggest-hub-card">
          <span className="suggest-hub-icon" style={{ background: 'var(--accent)' }}>
            <Icon name="tag" size={26} strokeWidth={1.8} />
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">Заявить акцию</span>
            <span className="brand-card-meta">
              Видели акцию, которой нет в сервисе? Расскажите — модератор добавит
            </span>
          </span>
          <span className="chevron-right"><Icon name="chevronRight" size={20} /></span>
        </Link>
        <Link to="/suggest/restaurant" className="suggest-hub-card">
          <span className="suggest-hub-icon" style={{ background: 'var(--primary)' }}>
            <Icon name="pin" size={26} strokeWidth={1.8} />
          </span>
          <span className="brand-card-body">
            <span className="brand-card-title">Добавить ресторан</span>
            <span className="brand-card-meta">
              Точки нет на карте? Укажите адрес и место — добавим после проверки
            </span>
          </span>
          <span className="chevron-right"><Icon name="chevronRight" size={20} /></span>
        </Link>
      </div>

      {pending !== null && pending > 0 && (
        <Link to="/profile" className="suggest-pending">
          <Icon name="inbox" size={18} />
          <span>
            {pending === 1
              ? 'Одна ваша заявка на модерации'
              : `Ваших заявок на модерации: ${pending}`}
          </span>
          <span className="chevron-right"><Icon name="chevronRight" size={18} /></span>
        </Link>
      )}

      <div className="section-title">Как это работает</div>
      <ol className="suggest-steps">
        <li>
          <span className="suggest-step-num">1</span>
          <span>
            Вы описываете акцию или точку — фото и ссылок не нужно, хватит
            названия и адреса
          </span>
        </li>
        <li>
          <span className="suggest-step-num">2</span>
          <span>
            Модератор города проверяет заявку. Статус виден в профиле, там же
            будет комментарий, если что-то не так
          </span>
        </li>
        <li>
          <span className="suggest-step-num">3</span>
          <span>
            Одобренная заявка появляется у всех в городе, а вам идут очки
            рейтинга
          </span>
        </li>
      </ol>
    </div>
  );
}
