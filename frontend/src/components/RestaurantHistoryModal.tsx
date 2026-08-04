import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useDismiss } from '../hooks/useDismiss';
import type { RestaurantHistory, RestaurantShort } from '../types';
import { timeAgo } from '../utils/time';
import Icon from './Icon';
import Overlay from './Overlay';

export default function RestaurantHistoryModal({ restaurant, onClose }: { restaurant: RestaurantShort; onClose: () => void }) {
  const [history, setHistory] = useState<RestaurantHistory | null>(null);
  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);
  useEffect(() => {
    api.get<RestaurantHistory>(`/restaurants/${restaurant.id}/history`).then(setHistory).catch(() => setHistory({ days: 7, reports_count: 0, contributors_count: 0, last_report_at: null, items: [] }));
  }, [restaurant.id]);

  return <Overlay>
    <div className={`modal-overlay${closing ? ' closing' : ''}`} onClick={dismiss} onAnimationEnd={onAnimationEnd}>
      <div className={`modal${closing ? ' closing' : ''}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="modal-head">
          <div><h2>Сводка по точке</h2><div className="subtitle">{restaurant.address} · последние 7 дней</div></div>
          <button className="modal-close" onClick={dismiss} aria-label="Закрыть"><Icon name="close" size={20} /></button>
        </div>
        <div className="modal-body history-body">
          {history === null ? <div className="skeleton skeleton-row" /> : history.reports_count === 0 ? (
            <div className="empty-state">За последние 7 дней точку ещё не проверяли</div>
          ) : <>
            <div className="history-summary">
              <div><strong>{history.reports_count}</strong><span>отчётов</span></div>
              <div><strong>{history.contributors_count}</strong><span>участников</span></div>
              <div><strong>{timeAgo(history.last_report_at) ?? '—'}</strong><span>последний</span></div>
            </div>
            <div className="history-note">Процент показывает долю отметок «есть», а не гарантирует наличие сейчас.</div>
            {history.items.map((item) => (
              <div className="history-item" key={`${item.promotion_title}-${item.item_name}`}>
                <div className="history-item-head"><span><strong>{item.item_name}</strong><small>{item.promotion_title}</small></span><b>{item.availability_percent}%</b></div>
                <div className="history-bar"><span style={{ width: `${item.availability_percent}%` }} /></div>
                <div className="muted">«Есть»: {item.available_count} из {item.reports_count}{item.last_available_at ? ` · последний раз ${timeAgo(item.last_available_at)}` : ''}</div>
              </div>
            ))}
          </>}
        </div>
      </div>
    </div>
  </Overlay>;
}
