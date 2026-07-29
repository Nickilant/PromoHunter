import { ReactNode, useState } from 'react';

interface Props {
  title: string;
  color?: string | null;
  count: number;
  badge?: ReactNode;
  children: ReactNode;
}

// Группа по бренду: свёрнута по умолчанию, раскрывается по клику
export default function CollapsibleGroup({ title, color, count, badge, children }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <div className="admin-group">
      <button className="admin-group-toggle" onClick={() => setOpen(!open)}>
        {color && <span className="color-dot" style={{ background: color }} />}
        <span className="admin-group-title">{title}</span>
        {badge}
        <span className="tag">{count}</span>
        <span className={`chevron ${open ? 'open' : ''}`}>▾</span>
      </button>
      {open && <div className="admin-group-body">{children}</div>}
    </div>
  );
}
