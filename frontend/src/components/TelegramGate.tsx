import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError, getToken } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import type { AuthResponse } from '../types';

// Автовход при открытии через Telegram WebApp:
// 1) initData -> вход по привязанному аккаунту;
// 2) аккаунт не привязан -> requestContact (номер из Telegram, он же проверка);
// 3) номер скрыт / отказ -> обычная авторизация.
export default function TelegramGate() {
  const { user, loading, applyAuth } = useAuth();
  const { city } = useCity();
  const navigate = useNavigate();
  const attempted = useRef(false);

  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp || !webApp.initData) return; // открыто не из Telegram
    webApp.ready();
    webApp.expand();

    if (loading || user || getToken() || attempted.current) return;
    attempted.current = true;

    const fallbackToLogin = () => navigate('/login');

    api
      .post<AuthResponse>('/auth/telegram', { init_data: webApp.initData, city })
      .then(applyAuth)
      .catch((err) => {
        const notLinked = err instanceof ApiError && err.status === 404;
        if (notLinked && webApp.requestContact) {
          webApp.requestContact((shared, event) => {
            const response = event?.response;
            if (shared && response) {
              api
                .post<AuthResponse>('/auth/telegram/contact', {
                  init_data: webApp.initData,
                  contact_response: response,
                  city,
                })
                .then(applyAuth)
                .catch(fallbackToLogin);
            } else {
              // номер скрыт или пользователь отказал
              fallbackToLogin();
            }
          });
        } else if (notLinked) {
          fallbackToLogin();
        }
        // прочие ошибки (например, TG не настроен на бэке) — молча,
        // пользователь может войти обычным способом
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  return null;
}
