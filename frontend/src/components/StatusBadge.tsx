import type { ItemStatus } from '../types';
import Icon from './Icon';
import type { IconName } from './Icon';

const LABELS: Record<ItemStatus, { text: string; icon: IconName }> = {
  available: { text: 'Есть', icon: 'check' },
  unavailable: { text: 'Кончилось', icon: 'close' },
  maybe_gone: { text: 'Возможно кончилось', icon: 'arrowDown' },
  maybe_appeared: { text: 'Возможно появилось', icon: 'arrowUp' },
  disputed: { text: 'Спорно', icon: 'question' },
  unknown: { text: 'Нет данных', icon: 'question' },
};

export default function StatusBadge({ status }: { status: ItemStatus }) {
  const { text, icon } = LABELS[status];
  return (
    <span className={`status-badge ${status}`}>
      <Icon name={icon} size={13} strokeWidth={2.4} />
      {text}
    </span>
  );
}
