import { ReactNode } from 'react';
import { createPortal } from 'react-dom';

/**
 * Обёртка для всех оверлеев: рендерит их порталом в конец `body`.
 *
 * Зачем: карта живёт в `position: fixed` контейнере с составными слоями
 * Leaflet, и вложенный в него оверлей перестаёт предсказуемо перекрывать
 * плавающий док — браузер собирает слои раньше, чем сравнивает z-index.
 * Из корня документа порядок наложения однозначен, и правило «оверлей выше
 * дока» работает на любой странице.
 */
export default function Overlay({ children }: { children: ReactNode }) {
  return createPortal(children, document.body);
}
