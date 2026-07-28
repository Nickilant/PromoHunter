import type { ItemStatus } from '../types';

const LABELS: Record<ItemStatus, string> = {
  available: 'Есть',
  unavailable: 'Кончилось',
  maybe_gone: '↓ Возможно кончилось',
  maybe_appeared: '↑ Возможно появилось',
  disputed: 'Спорно',
  unknown: 'Нет данных',
};

export default function StatusBadge({ status }: { status: ItemStatus }) {
  return <span className={`status-badge ${status}`}>{LABELS[status]}</span>;
}
