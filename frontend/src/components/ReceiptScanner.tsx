import { useEffect, useRef, useState } from 'react';

import Icon from './Icon';
import { safe, supports, webApp } from '../utils/telegram';

/**
 * Считывание QR с кассового чека средствами платформы:
 *
 * 1. штатный сканер Telegram — работает и на iOS, и на Android;
 * 2. BarcodeDetector по снимку с камеры — там, где браузер умеет.
 *
 * Своей библиотеки распознавания не тянем: лишняя зависимость ради того,
 * что уже есть у платформы. Ручного ввода строки нет намеренно — человек
 * стоит на точке с чеком в руках, переписывать её незачем.
 */

const HINT = 'Отсканируйте QR на кассовом чеке';

// Штатный сканер появился в Bot API 6.4. На клиентах постарше метод в SDK
// есть, но при вызове бросает WebAppMethodUnsupported — проверять наличие
// функции недостаточно, нужна версия.
const SCANNER_API = '6.4';

function telegramScanner(): TelegramWebApp | null {
  return supports(SCANNER_API) ? webApp() : null;
}

function hasBarcodeDetector(): boolean {
  return typeof BarcodeDetector !== 'undefined';
}

interface Props {
  onScanned: (raw: string) => void;
  disabled?: boolean;
}

export default function ReceiptScanner({ onScanned, disabled }: Props) {
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // Если мини-апп закрыли с открытым сканером — не оставляем его висеть.
  // Вызов обязательно через safe: на клиентах до 6.4 он бросает исключение,
  // а исключение из размонтирования уносит всё дерево в белый экран.
  useEffect(
    () => () => {
      if (supports(SCANNER_API)) safe(() => webApp()?.closeScanQrPopup?.());
    },
    [],
  );

  const scanInTelegram = () => {
    const app = telegramScanner();
    if (!app?.showScanQrPopup) return;
    setError(null);
    safe(() =>
      app.showScanQrPopup!({ text: HINT }, (text) => {
        if (!text) return false;
        safe(() => app.closeScanQrPopup?.());
        safe(() => app.HapticFeedback?.impactOccurred?.('light'));
        onScanned(text);
        return true; // закрыть попап
      }),
    );
  };

  const scanFromPhoto = async (file: File) => {
    setError(null);
    setReading(true);
    try {
      const detector = new BarcodeDetector({ formats: ['qr_code'] });
      const bitmap = await createImageBitmap(file);
      const codes = await detector.detect(bitmap);
      bitmap.close?.();
      if (codes.length === 0) {
        setError('QR на снимке не нашёлся — попробуйте снять ближе и ровнее');
        return;
      }
      onScanned(codes[0].rawValue);
    } catch {
      setError('Не получилось прочитать снимок — попробуйте ещё раз');
    } finally {
      setReading(false);
    }
  };

  if (telegramScanner()) {
    return (
      <div className="receipt-scanner">
        <button
          className="btn btn-primary btn-block"
          onClick={scanInTelegram}
          disabled={disabled}
        >
          <Icon name="qr" size={18} strokeWidth={2} />
          Сканировать чек
        </button>
        {error && <div className="form-error">{error}</div>}
      </div>
    );
  }

  if (hasBarcodeDetector()) {
    return (
      <div className="receipt-scanner">
        <button
          className={`btn btn-primary btn-block${reading ? ' is-busy' : ''}`}
          onClick={() => fileInput.current?.click()}
          disabled={disabled || reading}
          aria-busy={reading}
        >
          {reading ? (
            <span className="spinner" />
          ) : (
            <Icon name="qr" size={18} strokeWidth={2} />
          )}
          {reading ? 'Читаем…' : 'Сканировать чек'}
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="image/*"
          capture="environment"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = '';
            if (file) void scanFromPhoto(file);
          }}
        />
        {error && <div className="form-error">{error}</div>}
      </div>
    );
  }

  // Ни Telegram, ни камеры в браузере: честно говорим, где сканер есть
  return (
    <div className="capture-attach-hint">
      <Icon name="qr" size={16} />
      Сканер чека доступен в Telegram-приложении и в мобильном браузере с
      камерой — откройте точку оттуда
    </div>
  );
}
