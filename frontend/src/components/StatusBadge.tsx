import type { ItemStatus } from '../types';

const LABELS: Record<ItemStatus, string> = {
  available: 'Есть',
  unavailable: 'Кончилось',
  disputed: 'Спорно',
  unknown: 'Нет данных',
};

export default function StatusBadge({ status }: { status: ItemStatus }) {
  return <span className={`status-badge ${status}`}>{LABELS[status]}</span>;
}
