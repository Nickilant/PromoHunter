import { ReactNode, useState } from 'react';

import Icon from './Icon';

interface Props {
  title: string;
  /** Число в заголовке: сколько всего внутри */
  count?: number;
  defaultOpen?: boolean;
  children: ReactNode;
}

/**
 * Сворачиваемая секция профиля. Списки отчётов, подписок и заявок растут, и
 * без сворачивания страница превращается в бесконечную ленту, по которой
 * с телефона не долистать до настроек.
 */
export default function ProfileSection({
  title,
  count,
  defaultOpen = false,
  children,
}: Props) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="profile-section">
      <button
        className="profile-section-head"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className="profile-section-title">{title}</span>
        {count !== undefined && count > 0 && (
          <span className="profile-section-count">{count}</span>
        )}
        <span className={`chevron ${open ? 'open' : ''}`}>
          <Icon name="chevronDown" size={18} />
        </span>
      </button>
      {open && <div className="profile-section-body">{children}</div>}
    </div>
  );
}
