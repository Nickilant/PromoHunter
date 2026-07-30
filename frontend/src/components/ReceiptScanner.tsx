import { useEffect, useRef, useState } from 'react';

import Icon from './Icon';

/**
 * Получение строки QR с кассового чека тремя способами по убыванию удобства:
 *
 * 1. штатный сканер Telegram — работает и на iOS, и на Android;
 * 2. BarcodeDetector по снимку с камеры — там, где браузер умеет (Chrome);
 * 3. ручной ввод строки — всегда, как последний рубеж.
 *
 * Своей библиотеки распознавания не тянем: лишняя зависимость ради того,
 * что уже есть у платформы.
 */

const HINT = 'Отсканируйте QR на кассовом чеке';

function telegramScanner() {
  return window.Telegram?.WebApp?.showScanQrPopup ? window.Telegram.WebApp : null;
}

function hasBarcodeDetector(): boolean {
  return typeof BarcodeDetector !== 'undefined';
}

interface Props {
  onScanned: (raw: string) => void;
  disabled?: boolean;
}

export default function ReceiptScanner({ onScanned, disabled }: Props) {
  const [manual, setManual] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  // Если мини-апп закрыли с открытым сканером — не оставляем его висеть
  useEffect(() => () => window.Telegram?.WebApp?.closeScanQrPopup?.(), []);

  const scanInTelegram = () => {
    const app = telegramScanner();
    if (!app?.showScanQrPopup) return;
    setError(null);
    app.showScanQrPopup({ text: HINT }, (text) => {
      if (!text) return false;
      app.closeScanQrPopup?.();
      app.HapticFeedback?.impactOccurred?.('light');
      onScanned(text);
      return true; // закрыть попап
    });
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
        setError('QR на снимке не нашёлся — попробуйте ближе или введите вручную');
        return;
      }
      onScanned(codes[0].rawValue);
    } catch {
      setError('Не получилось прочитать снимок — введите строку вручную');
    } finally {
      setReading(false);
    }
  };

  const submitManual = () => {
    const text = value.trim();
    if (!text) {
      setError('Вставьте строку из QR-кода');
      return;
    }
    setError(null);
    onScanned(text);
  };

  const inTelegram = telegramScanner() !== null;

  return (
    <div className="receipt-scanner">
      {!manual && (
        <>
          {inTelegram ? (
            <button
              className="btn btn-primary btn-block"
              onClick={scanInTelegram}
              disabled={disabled}
            >
              <Icon name="qr" size={18} strokeWidth={2} />
              Сканировать чек
            </button>
          ) : hasBarcodeDetector() ? (
            <>
              <button
                className={`btn btn-primary btn-block${reading ? ' is-busy' : ''}`}
                onClick={() => fileInput.current?.click()}
                disabled={disabled || reading}
                aria-busy={reading}
              >
                {reading ? <span className="spinner" /> : <Icon name="qr" size={18} strokeWidth={2} />}
                {reading ? 'Читаем…' : 'Снять QR камерой'}
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
            </>
          ) : null}

          <button className="btn btn-ghost btn-block" onClick={() => setManual(true)}>
            <Icon name="receipt" size={17} />
            {inTelegram || hasBarcodeDetector()
              ? 'Ввести строку вручную'
              : 'Ввести строку с чека'}
          </button>
        </>
      )}

      {manual && (
        <div className="receipt-manual">
          <label className="field-label" htmlFor="receipt-raw">
            Строка из QR-кода чека
          </label>
          <textarea
            id="receipt-raw"
            className="text-input receipt-input"
            rows={3}
            placeholder="t=20260730T1830&s=349.00&fn=…&i=…&fp=…&n=1"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setError(null);
            }}
            spellCheck={false}
            autoCapitalize="off"
          />
          <div className="receipt-manual-actions">
            <button
              className="btn btn-primary"
              onClick={submitManual}
              disabled={disabled}
            >
              <Icon name="check" size={17} strokeWidth={2.2} />
              Готово
            </button>
            <button className="btn btn-ghost" onClick={() => setManual(false)}>
              Назад
            </button>
          </div>
        </div>
      )}

      {error && <div className="form-error">{error}</div>}
    </div>
  );
}
