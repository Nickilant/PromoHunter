// Мелкие игровые элементы, которые нужны в трёх местах сразу:
// в списках адресов, в модалке точки и на карте.
import { useCountdown } from '../hooks/useCountdown';
import type { Faction, PointControl } from '../types';
import {
  FACTION_THEY,
  FACTION_TITLE,
  formatEta,
  formatEtaShort,
  other,
  progressOf,
} from '../utils/faction';
import Icon from './Icon';

/** Плашка владения: кто держит точку (или что она свободна) */
export function OwnerChip({
  owner,
  size = 'normal',
}: {
  owner: Faction | null;
  size?: 'normal' | 'small';
}) {
  if (owner === null) {
    return (
      <span className={`faction-chip neutral${size === 'small' ? ' small' : ''}`}>
        <Icon name="flag" size={size === 'small' ? 12 : 14} strokeWidth={2} />
        Свободна
      </span>
    );
  }
  return (
    <span className={`faction-chip ${owner}${size === 'small' ? ' small' : ''}`}>
      <Icon name="shield" size={size === 'small' ? 12 : 14} strokeWidth={2} />
      {FACTION_TITLE[owner]}
    </span>
  );
}

interface TimerProps {
  point: PointControl;
  /** compact — для карты и строк списка, full — для панели точки */
  variant?: 'compact' | 'full';
}

/**
 * Таймер захвата. Тикает локально, поэтому одинаково выглядит и на карте,
 * и в списке, и не ждёт следующего запроса к серверу.
 */
export function CaptureTimer({ point, variant = 'compact' }: TimerProps) {
  const paused = !point.is_active_now || point.truce_seconds !== null;
  const left = useCountdown(point.eta_seconds, !paused);
  const truce = useCountdown(point.truce_seconds, true);

  if (point.truce_seconds !== null) {
    if (variant === 'compact') {
      return (
        <span className="capture-timer truce">
          <Icon name="shield" size={12} strokeWidth={2} />
          {formatEtaShort(truce)}
        </span>
      );
    }
    return (
      <span className="capture-timer truce full">
        <Icon name="shield" size={14} strokeWidth={2} />
        Перемирие ещё {formatEta(truce)}
      </span>
    );
  }

  if (point.leader === null || left === null) return null;

  const attacking = point.owner !== null && point.leader !== point.owner;
  const tone = attacking ? 'attack' : point.leader;

  if (variant === 'compact') {
    return (
      <span className={`capture-timer ${tone}${paused ? ' paused' : ''}`}>
        <Icon name={paused ? 'moon' : 'timer'} size={12} strokeWidth={2} />
        {paused ? 'пауза' : formatEtaShort(left)}
      </span>
    );
  }

  const who = attacking
    ? `Атакуют ${FACTION_THEY[point.leader]}`
    : point.owner === null
      ? `Занимают ${FACTION_THEY[point.leader]}`
      : 'Атака отбивается';

  return (
    <span className={`capture-timer full ${tone}${paused ? ' paused' : ''}`}>
      <Icon name={paused ? 'moon' : 'timer'} size={14} strokeWidth={2} />
      {paused ? 'Точка закрыта — шкалы стоят' : `${who} · ${formatEta(left)}`}
    </span>
  );
}

/** Две шкалы захвата друг под другом: чья заполнится первой, та и решила */
export function CaptureBars({ point }: { point: PointControl }) {
  const order: Faction[] = point.leader
    ? [point.leader, other(point.leader)]
    : ['green', 'purple'];
  return (
    <div className="capture-bars">
      {order.map((faction) => {
        const value = progressOf(point, faction);
        const isLeader = point.leader === faction && point.is_active_now;
        return (
          <div className="capture-bar-row" key={faction}>
            <span className="capture-bar-label">{FACTION_TITLE[faction]}</span>
            <span className="capture-bar-track">
              <span
                className={`capture-bar-fill ${faction}${isLeader ? ' moving' : ''}`}
                style={{ width: `${Math.round(value * 100)}%` }}
              />
            </span>
            <span className="capture-bar-value">{Math.round(value * 100)}%</span>
          </div>
        );
      })}
    </div>
  );
}

/** Соотношение сил: одна полоса, поделённая между сторонами */
export function ForceBar({ point }: { point: PointControl }) {
  const total = point.green_score + point.purple_score;
  const greenShare = total > 0 ? point.green_score / total : 0.5;
  return (
    <div className="force-bar" aria-hidden="true">
      <span className="force-green" style={{ flexGrow: greenShare || 0.001 }} />
      <span className="force-purple" style={{ flexGrow: 1 - greenShare || 0.001 }} />
    </div>
  );
}
