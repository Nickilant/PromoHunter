import { ReactNode, useLayoutEffect, useState } from 'react';
import { createPortal } from 'react-dom';

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
    return () => {
      host.remove();
    };
  }, [host]);

  return createPortal(children, host);
}
