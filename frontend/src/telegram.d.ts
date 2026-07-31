// Типы Telegram WebApp (подмножество, которое использует сервис)

interface TelegramContactEvent {
  status?: string;
  response?: string;
  responseUnsafe?: unknown;
}

interface TelegramWebApp {
  initData: string;
  /** Версия Bot API у клиента, например «6.0» */
  version?: string;
  isVersionAtLeast?: (version: string) => boolean;
  ready(): void;
  expand(): void;
  /** Отключает закрытие мини-аппа свайпом вниз по контенту (Bot API 7.7+) */
  disableVerticalSwipes?: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
  requestContact?: (
    callback: (shared: boolean, event?: TelegramContactEvent) => void,
  ) => void;
  /** Штатный сканер QR внутри Telegram (Bot API 6.4+) */
  showScanQrPopup?: (
    params: { text?: string },
    callback?: (text: string) => boolean | void,
  ) => void;
  closeScanQrPopup?: () => void;
  HapticFeedback?: {
    impactOccurred?: (style: 'light' | 'medium' | 'heavy') => void;
    notificationOccurred?: (type: 'error' | 'success' | 'warning') => void;
  };
}

/** BarcodeDetector есть в Chrome/Android; на iOS-Safari его нет */
interface BarcodeDetectorResult {
  rawValue: string;
}

declare class BarcodeDetector {
  constructor(options?: { formats?: string[] });
  detect(source: CanvasImageSource | Blob): Promise<BarcodeDetectorResult[]>;
  static getSupportedFormats(): Promise<string[]>;
}

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
