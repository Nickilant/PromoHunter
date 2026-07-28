import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import type {
  CityInfo,
  RatingCard,
  RatingPeriod,
  RatingResponse,
} from '../types';
import { formatDateTime } from '../utils/time';

const TYPE_LABELS: Record<string, string> = {
  report_base: 'Отчёты',
  report_confirmed: 'Подтверждённые отчёты',
  pioneer: 'Первопроходства',
  scout: 'Разведка новых точек',
  suggestion_approved: 'Одобренные заявки',
  report_refuted: 'Опровергнутые отчёты',
  suggestion_spam: 'Заявки-спам',
};

export default function RatingPage() {
  const { city: sessionCity } = useCity();
  const { user } = useAuth();
  const [city, setCity] = useState<string | null>(sessionCity);
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [period, setPeriod] = useState<RatingPeriod>('month');
  const [data, setData] = useState<RatingResponse | null>(null);
  const [card, setCard] = useState<RatingCard | null>(null);

  useEffect(() => {
    api.get<CityInfo[]>('/cities').then(setCities).catch(() => {});
  }, []);

  useEffect(() => {
    if (!city) return;
    setData(null);
    api
      .get<RatingResponse>(
        `/rating?city=${encodeURIComponent(city)}&period=${period}`,
      )
      .then(setData)
      .catch(() => setData({ entries: [], me: null }));
  }, [city, period]);

  const openCard = (userId: number) => {
    if (!city) return;
    setCard(null);
    api
      .get<RatingCard>(
        `/rating/users/${userId}?city=${encodeURIComponent(city)}&period=${period}`,
      )
      .then(setCard)
      .catch(() => {});
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Рейтинг</h1>
        <select
          className="city-chip"
          value={city ?? ''}
          onChange={(e) => setCity(e.target.value)}
        >
          {city && !cities.some((c) => c.name === city) && (
            <option value={city}>{city}</option>
          )}
          {cities.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="period-toggle">
        <button className={period === 'month' ? 'on' : ''} onClick={() => setPeriod('month')}>
          За месяц
        </button>
        <button className={period === 'year' ? 'on' : ''} onClick={() => setPeriod('year')}>
          За год
        </button>
      </div>

      {data === null && <div className="empty-state">Загружаем…</div>}

      {data !== null && data.entries.length === 0 && (
        <div className="empty-state">
          <div className="big">🏆</div>
          <div>
            В городе {city} пока никто не набрал очков. Отмечайте наличие
            товаров — и откроете этот рейтинг!
          </div>
        </div>
      )}

      {data?.entries.map((entry) => (
        <button
          key={entry.user_id}
          className={`rating-row ${user?.id === entry.user_id ? 'me' : ''}`}
          onClick={() => openCard(entry.user_id)}
        >
          <span className={`rating-pos ${entry.position <= 3 ? 'top' : ''}`}>
            {entry.position}
          </span>
          <span className="rating-body">
            <span className="brand-card-title">
              {entry.display_name}
              {user?.id === entry.user_id && ' (вы)'}
            </span>
            <span className="brand-card-meta">
              {entry.reports_count}{' '}
              {entry.reports_count === 1 ? 'отчёт' : 'отчётов'}
              {entry.pioneers_count > 0 &&
                ` · ${entry.pioneers_count} первопроходств`}
            </span>
          </span>
          <span className="rating-points">{entry.points}</span>
        </button>
      ))}

      {data?.me && user && (
        <div className="rating-me">
          {data.me.position !== null
            ? `Ваше место: ${data.me.position} · ${data.me.points} очков`
            : 'Вы пока не набрали очков в этом городе — начните с отчёта!'}
        </div>
      )}

      {card && (
        <div className="modal-overlay" onClick={() => setCard(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <h2>{card.display_name}</h2>
                <div className="subtitle">
                  {card.total_points} очков за {period === 'month' ? 'месяц' : 'год'}
                </div>
              </div>
              <button className="modal-close" onClick={() => setCard(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body" style={{ paddingBottom: 16 }}>
              {card.categories.length === 0 && (
                <div className="empty-state">Пока без очков</div>
              )}
              {card.categories.map((c) => (
                <div className="item-row" key={c.type}>
                  <span className="item-name">
                    {TYPE_LABELS[c.type] ?? c.type} × {c.count}
                  </span>
                  <span className={`rating-points ${c.points < 0 ? 'neg' : ''}`}>
                    {c.points > 0 ? `+${c.points}` : c.points}
                  </span>
                </div>
              ))}

              {card.events && card.events.length > 0 && (
                <>
                  <div className="section-title">Последние события</div>
                  {card.events.map((e, i) => (
                    <div className="list-item" key={i}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                        <span>{TYPE_LABELS[e.type] ?? e.type}</span>
                        <span className={`rating-points ${e.points < 0 ? 'neg' : ''}`}>
                          {e.points > 0 ? `+${e.points}` : e.points}
                        </span>
                      </div>
                      {e.context && <div className="muted">{e.context}</div>}
                      <div className="muted">{formatDateTime(e.created_at)}</div>
                    </div>
                  ))}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
