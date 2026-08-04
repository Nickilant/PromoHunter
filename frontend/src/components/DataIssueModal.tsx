import { useState } from 'react';

import { api } from '../api/client';
import { useDismiss } from '../hooks/useDismiss';
import type { RestaurantDetail } from '../types';
import Icon from './Icon';
import Overlay from './Overlay';

const TYPES = [
  ['closed', 'Ресторан закрыт навсегда'],
  ['temporarily_closed', 'Временно не работает'],
  ['wrong_address', 'Неверный адрес'],
  ['wrong_location', 'Неверная точка на карте'],
  ['duplicate', 'Дубликат ресторана'],
  ['moved', 'Ресторан переехал'],
  ['promotion_ended', 'Акция уже закончилась'],
  ['promotion_wrong', 'Ошибка в описании акции'],
  ['other', 'Другая ошибка'],
] as const;

export default function DataIssueModal({ restaurant, onClose }: { restaurant: RestaurantDetail; onClose: () => void }) {
  const [type, setType] = useState('wrong_address');
  const [promotionId, setPromotionId] = useState('');
  const [details, setDetails] = useState('');
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);
  const isPromotionIssue = type === 'promotion_ended' || type === 'promotion_wrong';
  const submit = async () => {
    if (details.trim().length < 5 || (isPromotionIssue && !promotionId)) return;
    setBusy(true); setError(null);
    try {
      await api.post('/issues', { restaurant_id: restaurant.id, promotion_id: promotionId ? Number(promotionId) : null, type, details: details.trim() });
      setDone(true);
    } catch (err) { setError(err instanceof Error ? err.message : 'Не удалось отправить сообщение'); }
    finally { setBusy(false); }
  };

  return <Overlay><div className={`modal-overlay${closing ? ' closing' : ''}`} onClick={dismiss} onAnimationEnd={onAnimationEnd}>
    <div className={`modal${closing ? ' closing' : ''}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
      <div className="modal-head"><div><h2>Сообщить об ошибке</h2><div className="subtitle">{restaurant.brand.name} · {restaurant.address}</div></div><button className="modal-close" onClick={dismiss} aria-label="Закрыть"><Icon name="close" size={20} /></button></div>
      {done ? <div className="modal-body"><div className="empty-state"><div className="big"><Icon name="checkCircle" size={44} /></div><div>Спасибо! Сообщение отправлено модератору.</div><button className="btn btn-primary" onClick={onClose}>Готово</button></div></div> : <>
        <div className="modal-body">
          <div className="field"><label>Что не так</label><select value={type} onChange={(e) => { setType(e.target.value); setPromotionId(''); }}>{TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
          {isPromotionIssue && <div className="field"><label>Акция</label><select value={promotionId} onChange={(e) => setPromotionId(e.target.value)}><option value="">Выберите акцию</option>{restaurant.promotions.map((promo) => <option value={promo.id} key={promo.id}>{promo.title}</option>)}</select></div>}
          <div className="field"><label>Подробности</label><textarea rows={4} maxLength={2000} value={details} onChange={(e) => setDetails(e.target.value)} placeholder="Опишите, что нужно проверить или исправить" /></div>
          {error && <div className="form-error">{error}</div>}
        </div>
        <div className="modal-footer"><button className="btn btn-primary btn-block" disabled={busy || details.trim().length < 5 || (isPromotionIssue && !promotionId)} onClick={submit}>{busy ? <span className="spinner" /> : 'Отправить модератору'}</button></div>
      </>}
    </div>
  </div></Overlay>;
}
