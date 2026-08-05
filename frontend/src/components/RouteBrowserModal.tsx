import { useState } from 'react';

import { useDismiss } from '../hooks/useDismiss';
import type { RoutePoint } from '../utils/yandexRoute';
import { yandexRouteWidgetUrl } from '../utils/yandexRoute';
import Icon from './Icon';
import Overlay from './Overlay';

interface Props {
  from: RoutePoint;
  to: RoutePoint;
  destination: string;
  onClose: () => void;
}

export default function RouteBrowserModal({ from, to, destination, onClose }: Props) {
  const [loading, setLoading] = useState(true);
  const { closing, dismiss, onAnimationEnd } = useDismiss(onClose);

  return (
    <Overlay>
      <section
        className={`route-browser${closing ? ' closing' : ''}`}
        aria-label={`Маршрут до ${destination}`}
        onAnimationEnd={onAnimationEnd}
      >
        <div className="route-browser-map">
          <button
            className="route-browser-back"
            onClick={dismiss}
            aria-label="Вернуться в PromoHunter"
          >
            <Icon name="arrowLeft" size={20} />
            <span>Назад</span>
          </button>
          {loading && (
            <div className="route-browser-loading" role="status">
              <span className="spinner" />
              Загружаем маршрут…
            </div>
          )}
          <iframe
            src={yandexRouteWidgetUrl(from, to)}
            title={`Яндекс Карты: маршрут до ${destination}`}
            allow="geolocation"
            referrerPolicy="strict-origin-when-cross-origin"
            onLoad={() => setLoading(false)}
          />
        </div>
      </section>
    </Overlay>
  );
}
