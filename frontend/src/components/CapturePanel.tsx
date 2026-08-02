import { useEffect, useState } from 'react';

import { api } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useGame } from '../hooks/useGame';
import type { PointControlDetail } from '../types';
import {
  FACTION_OF,
  FACTION_TITLE,
  other,
  pointSummary,
  receiptsOf,
  scoreOf,
} from '../utils/faction';
import { RECEIPTS, pluralize } from '../utils/plural';
import { CaptureBars, CaptureTimer, ForceBar, OwnerChip } from './GameBits';
import Icon from './Icon';

/**
 * Панель борьбы за точку внутри карточки: кто держит, соотношение сил,
 * две шкалы и таймер. Появляется только при включённом игровом режиме.
 */
export default function CapturePanel({ restaurantId }: { restaurantId: number }) {
  const { enabled, faction, pointOf, pointsVersion } = useGame();
  const { user } = useAuth();
  const [detail, setDetail] = useState<PointControlDetail | null>(null);
  const [open, setOpen] = useState(false);

  const summary = pointOf(restaurantId);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const path = user
      ? `/game/points/${restaurantId}/me`
      : `/game/points/${restaurantId}`;
    api
      .get<PointControlDetail>(path)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // pointsVersion — чтобы после своего чека панель показала новое состояние
  }, [enabled, restaurantId, user, pointsVersion]);

  if (!enabled) return null;
  // Боевое состояние берём из общего табло: оно обновляется сразу после
  // отправки чека. Деталь нужна ради собственного вклада и как запасной
  // источник, если точки этого города в табло ещё нет.
  const point = summary ?? detail;
  // Свободная точка тоже показывается: это приглашение её забрать, а не
  // пустая строка. В табло города её нет, пока за неё не воевали, поэтому
  // состояние приходит запросом — на это время держим место скелетоном,
  // чтобы карточка не дёргалась.
  if (!point) {
    return (
      <div className="capture-panel">
        <span
          className="skeleton on-surface"
          style={{ height: 24, margin: '10px 16px', borderRadius: 8, display: 'block' }}
        />
      </div>
    );
  }

  const mine = faction;
  const rival = mine ? other(mine) : null;
  const battle = point.leader !== null;

  return (
    <div className={`capture-panel${battle ? ' battle' : ''}`}>
      <button
        className="capture-panel-head"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <OwnerChip owner={point.owner} />
        <span className="capture-panel-state">{pointSummary(point)}</span>
        <CaptureTimer point={point} />
        <span className={`chevron${open ? ' open' : ''}`}>
          <Icon name="chevronDown" size={18} />
        </span>
      </button>

      {open && (
        <div className="capture-panel-body">
          <ForceBar point={point} />
          <div className="capture-forces">
            {(['green', 'purple'] as const).map((key) => (
              <div className={`capture-force ${key}`} key={key}>
                <span className="capture-force-title">
                  {FACTION_TITLE[key]}
                  {key === mine && <span className="capture-force-you">вы</span>}
                </span>
                <span className="capture-force-score">{scoreOf(point, key).toFixed(1)}</span>
                <span className="capture-force-meta">
                  {receiptsOf(point, key)} {pluralize(receiptsOf(point, key), RECEIPTS)}{' '}
                  всего
                </span>
              </div>
            ))}
          </div>

          {battle && <CaptureBars point={point} />}
          {battle && <CaptureTimer point={point} variant="full" />}

          {!point.is_active_now && (
            <div className="capture-note">
              <Icon name="moon" size={16} />
              Точка сейчас закрыта — шкалы захвата стоят до открытия
            </div>
          )}

          {detail && detail.my_receipts_today > 0 && (
            <div className="capture-note">
              <Icon name="receipt" size={16} />
              Ваш вклад за сутки: {detail.my_receipts_today}{' '}
              {pluralize(detail.my_receipts_today, RECEIPTS)}, сила{' '}
              {detail.my_strength_today.toFixed(2)}
            </div>
          )}

          {mine === null ? (
            <div className="capture-note">
              <Icon name="flag" size={16} />
              Выберите сторону в профиле, чтобы участвовать в захвате
            </div>
          ) : (
            <div className="capture-note">
              <Icon name="qr" size={16} />
              Чтобы добавить силу {FACTION_OF[mine]}, отметьте наличие и приложите
              чек — кнопка «Отметить» у акции
              {rival && point.owner === rival ? ', точка сейчас у соперника' : ''}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
