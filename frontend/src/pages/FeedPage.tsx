import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { api } from '../api/client';
import ReportModal from '../components/ReportModal';
import RestaurantCard from '../components/RestaurantCard';
import { useAuth } from '../hooks/useAuth';
import type { FeedEntry, PromotionWithStatuses, RestaurantShort } from '../types';

export default function FeedPage() {
  const [query, setQuery] = useState('');
  const [feed, setFeed] = useState<FeedEntry[] | null>(null);
  const [reportTarget, setReportTarget] = useState<{
    restaurant: RestaurantShort;
    promotion: PromotionWithStatuses;
  } | null>(null);
  const debounce = useRef<number | undefined>(undefined);
  const { user } = useAuth();
  const navigate = useNavigate();

  const load = useCallback((q: string) => {
    const params = q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
    api.get<FeedEntry[]>(`/feed${params}`).then(setFeed).catch(() => setFeed([]));
  }, []);

  useEffect(() => {
    load('');
  }, [load]);

  const onQueryChange = (value: string) => {
    setQuery(value);
    window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => load(value), 300);
  };

  const openReport = (restaurant: RestaurantShort, promotion: PromotionWithStatuses) => {
    if (!user) {
      navigate('/login');
      return;
    }
    setReportTarget({ restaurant, promotion });
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Акции</h1>
        <Link to="/suggest" className="btn btn-accent btn-small">
          + Заявить акцию
        </Link>
      </div>
      <input
        className="search-input"
        type="search"
        placeholder="Бренд, адрес, акция или товар…"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
      />

      {feed === null && <div className="empty-state">Загружаем…</div>}

      {feed !== null && feed.length === 0 && (
        <div className="empty-state">
          <div className="big">🔍</div>
          <div>
            {query.trim()
              ? 'Ничего не нашлось. Попробуйте другой запрос — или заявите акцию сами.'
              : 'Пока нет действующих акций. Видели что-то интересное? Расскажите!'}
          </div>
          <Link to="/suggest" className="btn btn-accent">
            Заявить акцию
          </Link>
        </div>
      )}

      {feed?.map((entry) => (
        <RestaurantCard key={entry.restaurant.id} entry={entry} onReport={openReport} />
      ))}

      {reportTarget && (
        <ReportModal
          restaurant={reportTarget.restaurant}
          promotion={reportTarget.promotion}
          onClose={() => setReportTarget(null)}
          onReported={() => load(query)}
        />
      )}
    </div>
  );
}
