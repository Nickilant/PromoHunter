import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import { useGame } from '../hooks/useGame';
import type {
  CityInfo,
  RatingCard,
  RatingEntry,
  RatingPeriod,
  RatingResponse,
  RatingScope,
} from '../types';
import { FACTION_TITLE } from '../utils/faction';
import { REPORTS, pluralize } from '../utils/plural';
import { formatDateTime } from '../utils/time';
import Icon from '../components/Icon';

const TYPE_LABELS: Record<string, string> = {
  report_base: 'Отчёты',
  report_confirmed: 'Подтверждённые отчёты',
  pioneer: 'Первопроходства',
  scout: 'Разведка новых точек',
  suggestion_approved: 'Одобренные акции',
  restaurant_approved: 'Добавленные рестораны',
  report_refuted: 'Опровергнутые отчёты',
  suggestion_spam: 'Заявки-спам',
  restaurant_spam: 'Заявки на рестораны — спам',
};

// Первая страница — ровно 10 мест, чтобы список влезал без прокрутки;
// «…» подгружает следующую десятку
const PAGE = 10;

/** Строка таблицы: одинаковая и в топе, и для своего места ниже «…» */
function Row({
  entry,
  me,
  onOpen,
}: {
  entry: RatingEntry;
  me: number | undefined;
  onOpen: (userId: number) => void;
}) {
  const isMe = me === entry.user_id;
  return (
    <button
      className={`rating-row${isMe ? ' me' : ''}`}
      onClick={() => onOpen(entry.user_id)}
    >
      <span className={`rating-pos ${entry.position <= 3 ? 'top' : ''}`}>
        {entry.position}
      </span>
      {/* Одна строка на место: только так десятка, «…» и своё место
          укладываются на экран без прокрутки */}
      <span className="rating-name">
        {entry.display_name}
        {isMe && <span className="rating-you">вы</span>}
      </span>
      <span className="rating-meta">
        {entry.reports_count} {pluralize(entry.reports_count, REPORTS)}
        {entry.pioneers_count > 0 && ` · ${entry.pioneers_count}★`}
      </span>
      <span className="rating-points">{entry.points}</span>
    </button>
  );
}

export default function RatingPage() {
  const { city: sessionCity } = useCity();
  const { user } = useAuth();
  const { faction } = useGame();
  const [city, setCity] = useState<string | null>(sessionCity);
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [period, setPeriod] = useState<RatingPeriod>('month');
  const [scope, setScope] = useState<RatingScope>('all');
  const [data, setData] = useState<RatingResponse | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [card, setCard] = useState<RatingCard | null>(null);

  useEffect(() => {
    api.get<CityInfo[]>('/cities').then(setCities).catch(() => {});
  }, []);

  // Сторону могли снять в профиле — зачёт по фракции тогда недоступен
  useEffect(() => {
    if (!faction) setScope('all');
  }, [faction]);

  const query = (limit: number, offset: number) =>
    `/rating?city=${encodeURIComponent(city!)}&period=${period}` +
    `&scope=${scope}&limit=${limit}&offset=${offset}`;

  useEffect(() => {
    if (!city) return;
    setData(null);
    api
      .get<RatingResponse>(query(PAGE, 0))
      .then(setData)
      .catch(() => setData({ entries: [], total: 0, me: null }));
    // query собирается из этих же значений
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [city, period, scope]);

  const loadMore = async () => {
    if (!city || !data || loadingMore) return;
    setLoadingMore(true);
    try {
      const next = await api.get<RatingResponse>(query(PAGE, data.entries.length));
      setData({
        ...next,
        entries: [...data.entries, ...next.entries],
      });
    } catch {
      /* не подгрузилось — список остаётся как был */
    } finally {
      setLoadingMore(false);
    }
  };

  const loaded = data?.entries.length ?? 0;
  const total = data?.total ?? 0;
  const myPosition = data?.me?.position ?? null;
  // Своя строка ниже выданной страницы — показываем её отдельно, после «…»
  const myRowBelow = myPosition !== null && myPosition > loaded;
  const hasGap = loaded < total;

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

      {/* Зачёт внутри своей фракции — только когда сторона выбрана.
          Компактный слайдер: он второстепенен рядом с выбором периода */}
      {faction && (
        <div className="scope-switch-row">
          <div className={`scope-switch ${faction}`} role="tablist" aria-label="Зачёт">
            <span
              className="scope-switch-thumb"
              style={{ transform: scope === 'faction' ? 'translateX(100%)' : 'none' }}
            />
            <button
              role="tab"
              aria-selected={scope === 'all'}
              className={scope === 'all' ? 'on' : ''}
              onClick={() => setScope('all')}
            >
              Все
            </button>
            <button
              role="tab"
              aria-selected={scope === 'faction'}
              className={scope === 'faction' ? 'on' : ''}
              onClick={() => setScope('faction')}
            >
              {FACTION_TITLE[faction]}
            </button>
          </div>
        </div>
      )}

      {data === null && (
        <div className="skeleton-list" aria-label="Загружаем рейтинг" aria-busy="true">
          {[0, 1, 2, 3, 4].map((i) => (
            <div className="skeleton skeleton-row" style={{ height: 62 }} key={i} />
          ))}
        </div>
      )}

      {data !== null && data.entries.length === 0 && (
        <div className="empty-state">
          <div className="big"><Icon name="trophy" size={44} strokeWidth={1.4} /></div>
          <div>
            В городе {city} пока никто не набрал очков. Отмечайте наличие
            товаров — и откроете этот рейтинг!
          </div>
        </div>
      )}

      {data !== null && data.entries.length > 0 && (
        <>
          <div className="rating-list">
            {data.entries.map((entry) => (
              <Row key={entry.user_id} entry={entry} me={user?.id} onOpen={openCard} />
            ))}

            {/* Между таблицей и своей строкой — многоточие, оно же кнопка
                «показать ещё десять» */}
            {hasGap && (
              <button
                className={`rating-gap${loadingMore ? ' is-busy' : ''}`}
                onClick={loadMore}
                disabled={loadingMore}
                aria-label="Показать ещё десять мест"
                title="Показать ещё десять мест"
              >
                {loadingMore ? <span className="spinner" /> : '…'}
              </button>
            )}
          </div>

          {/* Своя строка закреплена вне области прокрутки: место видно
              всегда, на каком угодно экране */}
          {myRowBelow && data.me && (
            <Row entry={data.me as RatingEntry} me={user?.id} onOpen={openCard} />
          )}
        </>
      )}

      {/* Админ в зачёте не участвует — иначе строка «нет очков» вводит в
          заблуждение: очки у него есть, просто он вне соревнования */}
      {user?.role === 'admin' && (
        <div className="rating-me">
          Администраторы в зачёте не участвуют — так честнее к остальным
        </div>
      )}

      {data?.me && user && user.role !== 'admin' && data.me.position === null && (
        <div className="rating-me">
          Вы пока не набрали очков в этом
          {scope === 'faction' ? ' зачёте' : ' городе'} — начните с отчёта!
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
              <button className="modal-close" onClick={() => setCard(null)} aria-label="Закрыть">
                <Icon name="close" size={20} />
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
