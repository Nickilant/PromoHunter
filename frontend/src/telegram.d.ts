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
  requestContact?: (
    callback: (shared: boolean, event?: TelegramContactEvent) => void,
  ) => void;
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
