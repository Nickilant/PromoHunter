// Единый набор иконок сервиса: контурные, 24×24, наследуют цвет через currentColor.
// Держим в одном файле — правки в одном месте, отдельных зависимостей не тянем.
//
// Лестница «размер → толщина обводки», чтобы набор выглядел ровно:
//   13px → 2.4 | 15–18px → 1.7 | 20–22px → 1.7 (активная вкладка 2.0)
//   24px → 2.2 | 26px → 1.8 | 44px (пустые состояния) → 1.4
// Цвет иконка всегда берёт от родителя (currentColor) — своего не имеет.
import type { CSSProperties, ReactNode } from 'react';

export type IconName =
  | 'tag'
  | 'map'
  | 'trophy'
  | 'user'
  | 'plus'
  | 'pin'
  | 'locate'
  | 'route'
  | 'search'
  | 'filter'
  | 'chart'
  | 'alert'
  | 'chevronDown'
  | 'chevronRight'
  | 'chevronLeft'
  | 'arrowLeft'
  | 'arrowUp'
  | 'arrowDown'
  | 'close'
  | 'check'
  | 'checkCircle'
  | 'crossCircle'
  | 'question'
  | 'bell'
  | 'bellOff'
  | 'store'
  | 'truck'
  | 'inbox'
  | 'send'
  | 'city'
  | 'logout'
  | 'lock'
  | 'ticket'
  | 'shield'
  | 'flag'
  | 'swords'
  | 'qr'
  | 'layers'
  | 'timer'
  | 'receipt'
  | 'gamepad'
  | 'moon';

const PATHS: Record<IconName, ReactNode> = {
  // навигация
  tag: (
    <>
      <path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8Z" />
      <circle cx="7.8" cy="7.8" r="1.4" />
    </>
  ),
  map: (
    <>
      <path d="M2 6.5 9 4l6 2.5L21.4 4v13.5L15 20l-6-2.5L2.6 20V6.5Z" />
      <path d="M9 4v13.5M15 6.5V20" />
    </>
  ),
  trophy: (
    <>
      <path d="M7 4h10v5a5 5 0 0 1-10 0V4Z" />
      <path d="M7 6H5a2 2 0 0 0 0 4h2M17 6h2a2 2 0 0 1 0 4h-2" />
      <path d="M12 14v3M8.5 20h7M9.5 20a2.5 2.5 0 0 1 2.5-3 2.5 2.5 0 0 1 2.5 3" />
    </>
  ),
  user: (
    <>
      <circle cx="12" cy="8" r="3.6" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </>
  ),
  plus: <path d="M12 5.5v13M5.5 12h13" />,

  // география и поиск
  pin: (
    <>
      <path d="M20 10.5c0 5.5-8 11-8 11s-8-5.5-8-11a8 8 0 0 1 16 0Z" />
      <circle cx="12" cy="10.3" r="2.7" />
    </>
  ),
  locate: (
    <>
      <circle cx="12" cy="12" r="7.2" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M12 1.8v3.2M12 19v3.2M1.8 12H5m14 0h3.2" />
    </>
  ),
  search: (
    <>
      <circle cx="10.8" cy="10.8" r="6.4" />
      <path d="m20 20-4.6-4.6" />
    </>
  ),
  route: (
    <>
      <circle cx="6" cy="18" r="2.2" />
      <circle cx="18" cy="6" r="2.2" />
      <path d="M8.2 18h2.3a2 2 0 0 0 2-2v-2a2 2 0 0 1 2-2H16M13.5 6H10a2 2 0 0 0-2 2v2" />
      <path d="m15 9 3-3-3-3" />
    </>
  ),
  filter: (
    <>
      <path d="M4 6h16M7 12h10M10 18h4" />
    </>
  ),
  chart: (
    <>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </>
  ),
  alert: (
    <>
      <path d="M10.2 4.2 2.8 17a2 2 0 0 0 1.7 3h15a2 2 0 0 0 1.7-3L13.8 4.2a2 2 0 0 0-3.6 0Z" />
      <path d="M12 9v4M12 16.5v.01" />
    </>
  ),
  city: (
    <>
      <path d="M3 20.5h18" />
      <path d="M4.5 20.5V9.5l6-3.5v14.5" />
      <path d="M10.5 20.5V11l8 2.5v7" />
      <path d="M7.3 11.2v.01M7.3 14.6v.01M14.3 15.4v.01M14.3 18v.01" />
    </>
  ),

  // стрелки и шевроны
  chevronDown: <path d="m6.5 9.5 5.5 5.5 5.5-5.5" />,
  chevronRight: <path d="m9.5 6.5 5.5 5.5-5.5 5.5" />,
  chevronLeft: <path d="M14.5 6.5 9 12l5.5 5.5" />,
  arrowLeft: <path d="M19 12H5.5m0 0 5.5-5.5M5.5 12 11 17.5" />,
  arrowUp: <path d="M12 19V5.5m0 0L6.5 11M12 5.5 17.5 11" />,
  arrowDown: <path d="M12 5v13.5m0 0L6.5 13M12 18.5 17.5 13" />,

  // статусы и действия
  close: <path d="m17.5 6.5-11 11m0-11 11 11" />,
  check: <path d="m5 12.5 4.8 4.8L19 7.5" />,
  checkCircle: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.2 12.2 2.6 2.6 5-5.2" />
    </>
  ),
  crossCircle: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m9.4 9.4 5.2 5.2m0-5.2-5.2 5.2" />
    </>
  ),
  question: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.9 9.6a2.2 2.2 0 1 1 3 2.1c-.6.3-.9.8-.9 1.5v.4" />
      <path d="M12 16.6v.01" />
    </>
  ),

  // подписки
  bell: (
    <>
      <path d="M18 15.5c0-5.5-1-9-6-9s-6 3.5-6 9H4.8L4 17.2h16l-.8-1.7H18Z" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
    </>
  ),
  bellOff: (
    <>
      <path d="M18 15.5c0-3.4-.4-6.1-2.3-7.7M8.2 8c-1.6 1.6-2.2 4-2.2 7.5H4.8L4 17.2h13" />
      <path d="M10 20a2.2 2.2 0 0 0 4 0" />
      <path d="m4.5 4.5 15 15" />
    </>
  ),

  // каналы отчёта
  store: (
    <>
      <path d="M4 9.5 5.4 4.5h13.2L20 9.5" />
      <path d="M5.4 9.5V20h13.2V9.5" />
      <path d="M4 9.5h16" />
      <path d="M9.6 20v-5.2h4.8V20" />
    </>
  ),
  truck: (
    <>
      <path d="M2.8 6h11v10.5h-11z" />
      <path d="M13.8 9.5h3.6l2.8 3v4h-6.4" />
      <circle cx="7" cy="18.2" r="1.9" />
      <circle cx="17.2" cy="18.2" r="1.9" />
    </>
  ),

  // прочее
  inbox: (
    <>
      <path d="M3.5 13h4l1.6 2.4h5.8L16.5 13h4" />
      <path d="M6.6 4.8h10.8l3.1 8.2v5.2a1.8 1.8 0 0 1-1.8 1.8H5.3a1.8 1.8 0 0 1-1.8-1.8V13l3.1-8.2Z" />
    </>
  ),
  send: (
    <>
      <path d="M20.5 3.5 3.8 10.2l6.3 2.6 2.6 6.3 7.8-15.6Z" />
      <path d="M20.5 3.5 10.1 12.8" />
    </>
  ),
  logout: (
    <>
      <path d="M14.5 8V5.6a1.8 1.8 0 0 0-1.8-1.8H5.8A1.8 1.8 0 0 0 4 5.6v12.8a1.8 1.8 0 0 0 1.8 1.8h6.9a1.8 1.8 0 0 0 1.8-1.8V16" />
      <path d="M20 12H9.5m10.5 0-3.4-3.4M20 12l-3.4 3.4" />
    </>
  ),

  // Купон с фигурным вырезом по бокам — узнаваемая форма скидки
  ticket: (
    <>
      <path d="M3.6 9.2V6.8a1.6 1.6 0 0 1 1.6-1.6h13.6a1.6 1.6 0 0 1 1.6 1.6v2.4a2.8 2.8 0 0 0 0 5.6v2.4a1.6 1.6 0 0 1-1.6 1.6H5.2a1.6 1.6 0 0 1-1.6-1.6v-2.4a2.8 2.8 0 0 0 0-5.6Z" />
      <path d="M14 8.6v1.6m0 3.6v1.6" />
    </>
  ),
  lock: (
    <>
      <rect x="4.2" y="10.4" width="15.6" height="10" rx="2.2" />
      <path d="M8 10.4V7.6a4 4 0 0 1 8 0v2.8" />
    </>
  ),

  // игровой режим
  shield: (
    <>
      <path d="M12 3.2l7 2.6v5.4c0 4.4-3 7.9-7 9.6-4-1.7-7-5.2-7-9.6V5.8l7-2.6Z" />
    </>
  ),
  flag: (
    <>
      <path d="M6 20.5V4" />
      <path d="M6 4.6h9.6l-1.4 3.6 1.4 3.6H6" />
    </>
  ),
  // Два скрещённых клинка: рукояти внизу, острия в верхних углах
  swords: (
    <>
      <path d="M20 4.2 10.6 13.6M4 4.2l9.4 9.4" />
      <path d="M16.6 4.2H20v3.4M7.4 4.2H4v3.4" />
      <path d="m6.7 17.3 3.2-3.2 1.6 1.6-3.2 3.2a1.15 1.15 0 0 1-1.6-1.6Z" />
      <path d="m17.3 17.3-3.2-3.2-1.6 1.6 3.2 3.2a1.15 1.15 0 0 0 1.6-1.6Z" />
    </>
  ),
  // Два «глаза» QR по углам и рамка-уголки: читается даже в 16px
  qr: (
    <>
      <rect x="3.6" y="3.6" width="6.4" height="6.4" rx="1.4" />
      <rect x="14" y="3.6" width="6.4" height="6.4" rx="1.4" />
      <rect x="3.6" y="14" width="6.4" height="6.4" rx="1.4" />
      <path d="M14 14h2.6v2.6H14zM17.8 17.8h2.6v2.6h-2.6z" />
    </>
  ),
  layers: (
    <>
      <path d="M12 3.5 20 8l-8 4.5L4 8l8-4.5Z" />
      <path d="m4.6 12.4 7.4 4.2 7.4-4.2" />
    </>
  ),
  timer: (
    <>
      <circle cx="12" cy="13.2" r="7.6" />
      <path d="M12 9.6v3.6l2.4 1.6" />
      <path d="M9.4 3.4h5.2" />
    </>
  ),
  receipt: (
    <>
      <path d="M6 3.6h12v16.8l-2.4-1.5-2.4 1.5-2.4-1.5-2.4 1.5L6 20.4V3.6Z" />
      <path d="M9.2 8h5.6M9.2 11.6h5.6" />
    </>
  ),
  gamepad: (
    <>
      <path d="M8.4 8h7.2a5.4 5.4 0 0 1 5.4 5.4c0 1.9-1.5 3.4-3.4 3.4-1.2 0-2.2-.7-3-1.5H9.4c-.8.8-1.8 1.5-3 1.5A3.4 3.4 0 0 1 3 13.4 5.4 5.4 0 0 1 8.4 8Z" />
      <path d="M7.6 11.4v2.4M6.4 12.6h2.4" />
      <path d="M15.6 12.6v.01M17.6 12.6v.01" />
    </>
  ),
  moon: <path d="M20 14.4A8.4 8.4 0 0 1 9.6 4a8.4 8.4 0 1 0 10.4 10.4Z" />,
};

interface Props {
  name: IconName;
  size?: number;
  /** Толщина обводки; мелкие иконки читаются лучше с чуть большей */
  strokeWidth?: number;
  className?: string;
  style?: CSSProperties;
}

export default function Icon({ name, size = 20, strokeWidth = 1.7, className, style }: Props) {
  return (
    <svg
      className={className}
      style={style}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {PATHS[name]}
    </svg>
  );
}

/** Знак сервиса: ценник в мягком круге — для экранов входа и пустых состояний */
export function LogoMark({ size = 64 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none" aria-hidden="true">
      <rect width="64" height="64" rx="20" fill="var(--primary-soft)" />
      <path
        d="M43.5 33.2 33.2 43.5a2.6 2.6 0 0 1-3.7 0L19 33V19h14l10.5 10.5a2.6 2.6 0 0 1 0 3.7Z"
        stroke="var(--primary)"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <circle cx="26" cy="26" r="2.6" fill="var(--accent)" />
    </svg>
  );
}
