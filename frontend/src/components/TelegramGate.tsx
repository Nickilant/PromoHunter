import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

import { api, ApiError, getToken } from '../api/client';
import { useAuth } from '../hooks/useAuth';
import { useCity } from '../hooks/useCity';
import type { AuthResponse } from '../types';
import { attempt, safe, webApp } from '../utils/telegram';

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
    const app = webApp();
    if (!app || !app.initData) return; // открыто не из Telegram
    // Всё ниже — методы разных версий Bot API. На старом клиенте они есть в
    // SDK, но при вызове бросают WebAppMethodUnsupported, поэтому идут через
    // safe: оформление мини-аппа не стоит того, чтобы уронить приложение.
    safe(() => app.ready());
    safe(() => app.expand());
    // Свайп по списку/карте не должен закрывать мини-апп (7.7+)
    safe(() => app.disableVerticalSwipes?.());
    // Шапка Telegram в тон приложения (6.1+)
    safe(() => app.setHeaderColor?.('#F7F5F2'));
    safe(() => app.setBackgroundColor?.('#F7F5F2'));

    if (loading || user || getToken() || attempted.current) return;
    attempted.current = true;

    const fallbackToLogin = () => navigate('/login');

    api
      .post<AuthResponse>('/auth/telegram', { init_data: app.initData, city })
      .then(applyAuth)
      .catch((err) => {
        const notLinked = err instanceof ApiError && err.status === 404;
        if (!notLinked) return;
        // requestContact — 6.9+; на клиенте постарше вызов бросит исключение,
        // и тогда остаётся обычный вход по номеру и паролю
        const asked =
          !!app.requestContact &&
          attempt(() =>
            app.requestContact!((shared, event) => {
              const response = event?.response;
              if (shared && response) {
                api
                  .post<AuthResponse>('/auth/telegram/contact', {
                    init_data: app.initData,
                    contact_response: response,
                    city,
                  })
                  .then(applyAuth)
                  .catch(fallbackToLogin);
              } else {
                // номер скрыт или пользователь отказал
                fallbackToLogin();
              }
            }),
          );
        if (!asked) fallbackToLogin();
        // прочие ошибки (например, TG не настроен на бэке) — молча,
        // пользователь может войти обычным способом
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  return null;
}
