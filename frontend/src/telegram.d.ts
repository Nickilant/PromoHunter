// Типы Telegram WebApp (подмножество, которое использует сервис)

interface TelegramContactEvent {
  status?: string;
  response?: string;
  responseUnsafe?: unknown;
}

interface TelegramWebApp {
  initData: string;
  ready(): void;
  expand(): void;
  /** Отключает закрытие мини-аппа свайпом вниз по контенту (Bot API 7.7+) */
  disableVerticalSwipes?: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  requestContact?: (
    callback: (shared: boolean, event?: TelegramContactEvent) => void,
  ) => void;
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
