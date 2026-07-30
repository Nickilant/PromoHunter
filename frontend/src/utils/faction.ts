import type { Faction, PointControl } from '../types';

export const FACTION_TITLE: Record<Faction, string> = {
  green: 'Зелёные',
  purple: 'Фиолетовые',
};

/** Родительный падеж — для фраз вида «точка зелёных», «силу зелёных» */
export const FACTION_OF: Record<Faction, string> = {
  green: 'зелёных',
  purple: 'фиолетовых',
};

/** Именительный со строчной — когда фракция подлежащее: «атакуют зелёные» */
export const FACTION_THEY: Record<Faction, string> = {
  green: 'зелёные',
  purple: 'фиолетовые',
};

export const FACTION_COLOR: Record<Faction, string> = {
  green: 'var(--green-faction)',
  purple: 'var(--purple-faction)',
};

export const FACTION_INK: Record<Faction, string> = {
  green: 'var(--green-faction-ink)',
  purple: 'var(--purple-faction-ink)',
};

export const FACTION_SOFT: Record<Faction, string> = {
  green: 'var(--green-faction-soft)',
  purple: 'var(--purple-faction-soft)',
};

/** Цвет для canvas/SVG, где переменные CSS не работают (маркеры Leaflet) */
export const FACTION_HEX: Record<Faction, string> = {
  green: '#4F9D69',
  purple: '#8A6BBF',
};

export const NEUTRAL_HEX = '#B4ADA3';

export function other(faction: Faction): Faction {
  return faction === 'green' ? 'purple' : 'green';
}

export function scoreOf(point: PointControl, faction: Faction): number {
  return faction === 'green' ? point.green_score : point.purple_score;
}

export function receiptsOf(point: PointControl, faction: Faction): number {
  return faction === 'green' ? point.green_receipts : point.purple_receipts;
}

export function progressOf(point: PointControl, faction: Faction): number {
  return faction === 'green' ? point.green_progress : point.purple_progress;
}

/** Идёт ли за точку битва: есть шкала и есть кому её двигать */
export function inBattle(point: PointControl): boolean {
  return point.leader !== null;
}

/** «1 ч 40 мин» / «12 мин» — компактно, без секунд */
export function formatEta(seconds: number | null): string {
  if (seconds === null) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours} ч ${String(minutes).padStart(2, '0')} мин`;
  if (minutes > 0) return `${minutes} мин`;
  return `${total} с`;
}

/** Короткая форма для плашек на карте: «1:40» / «12м» */
export function formatEtaShort(seconds: number | null): string {
  if (seconds === null) return '—';
  const total = Math.max(0, Math.round(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return `${hours}:${String(minutes).padStart(2, '0')}`;
  return `${minutes || Math.ceil(total / 60)}м`;
}

/** Человеческое описание, что сейчас с точкой */
export function pointSummary(point: PointControl): string {
  if (point.truce_seconds !== null) return 'Перемирие после отбитой атаки';
  if (point.leader === null) {
    return point.owner ? `Точка ${FACTION_OF[point.owner]}` : 'Точка свободна';
  }
  if (!point.is_active_now) return 'Точка закрыта — шкалы стоят';
  if (point.owner === null) return `${FACTION_TITLE[point.leader]} занимают точку`;
  if (point.leader === point.owner) return 'Атака отбивается';
  return `${FACTION_TITLE[point.leader]} захватывают точку`;
}
