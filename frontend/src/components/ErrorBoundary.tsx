import { Component, ErrorInfo, ReactNode } from 'react';

import { DEVELOPER_TELEGRAM_URL } from '../utils/contacts';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Последний рубеж: без него любая необработанная ошибка рендера уносит всё
 * дерево, и человек видит пустой экран без единой подсказки — «помогает только
 * перезагрузка». Показываем, что именно упало, и даём кнопку.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // В консоль — полный стек: по нему чинить, скриншота экрана мало
    console.error('Сбой интерфейса:', error, info.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="crash-screen">
        <h1>Что-то сломалось</h1>
        <p className="muted">
          Экран не смог отрисоваться. Перезагрузка обычно помогает — а текст
          ошибки ниже поможет починить причину.
        </p>
        <pre className="crash-detail">{error.message || String(error)}</pre>
        <button className="btn btn-primary btn-block" onClick={() => window.location.reload()}>
          Перезагрузить
        </button>
        <a
          className="btn btn-ghost btn-block"
          href={DEVELOPER_TELEGRAM_URL}
          target="_blank"
          rel="noreferrer"
        >
          Сообщить разработчику
        </a>
      </div>
    );
  }
}
