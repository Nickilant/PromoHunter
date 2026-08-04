import { ReactNode, useLayoutEffect, useState } from 'react';
import { createPortal } from 'react-dom';

let openOverlays = 0;
let lockedScrollY = 0;
let savedBodyStyles: Partial<CSSStyleDeclaration> = {};

function lockPageScroll() {
  if (openOverlays > 0) {
    openOverlays += 1;
    return;
  }
  openOverlays = 1;
  lockedScrollY = window.scrollY;
  savedBodyStyles = {
    position: document.body.style.position,
    top: document.body.style.top,
    left: document.body.style.left,
    right: document.body.style.right,
    width: document.body.style.width,
    overflow: document.body.style.overflow,
    paddingRight: document.body.style.paddingRight,
  };
  const scrollbarWidth = window.innerWidth - document.documentElement.clientWidth;
  document.body.style.position = 'fixed';
  document.body.style.top = `-${lockedScrollY}px`;
  document.body.style.left = '0';
  document.body.style.right = '0';
  document.body.style.width = '100%';
  document.body.style.overflow = 'hidden';
  if (scrollbarWidth > 0) document.body.style.paddingRight = `${scrollbarWidth}px`;
}

function unlockPageScroll() {
  openOverlays = Math.max(0, openOverlays - 1);
  if (openOverlays > 0) return;
  Object.assign(document.body.style, savedBodyStyles);
  window.scrollTo(0, lockedScrollY);
}

/**
 * Обёртка для всех оверлеев: рендерит их порталом поверх страницы.
 *
 * Зачем портал: карта живёт в `position: fixed` контейнере с составными слоями
 * Leaflet, и вложенный в него оверлей перестаёт предсказуемо перекрывать
 * плавающий док — браузер собирает слои раньше, чем сравнивает z-index.
 * Из корня документа порядок наложения однозначен.
 *
 * Зачем свой контейнер, а не сам `body`: оверлеи вкладываются друг в друга
 * (из карточки точки открывается отметка наличия), и тогда два портала целятся
 * в один и тот же `body`. React считает позицию вставки относительно соседей
 * внутри контейнера, и на размонтировании вложенного портала может убрать не
 * те узлы — вплоть до всего `#root`. Отдельный div на каждый оверлей убирает
 * этот класс ошибок целиком: React управляет только своим контейнером.
 */
export default function Overlay({ children }: { children: ReactNode }) {
  const [host] = useState(() => document.createElement('div'));

  useLayoutEffect(() => {
    host.className = 'overlay-host';
    document.body.appendChild(host);
    lockPageScroll();
    return () => {
      host.remove();
      unlockPageScroll();
    };
  }, [host]);

  return createPortal(children, host);
}
