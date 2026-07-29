import { useCallback, useEffect, useState } from 'react';

/**
 * Плавное закрытие оверлеев: вместо мгновенного анмаунта включаем класс
 * `closing`, а реальное закрытие делаем по окончании анимации.
 * Возвращает флаг для класса и обёрнутый обработчик закрытия.
 */
export function useDismiss(onClose?: () => void) {
  const [closing, setClosing] = useState(false);

  const dismiss = useCallback(() => {
    if (!onClose) return;
    setClosing(true);
  }, [onClose]);

  // Страховка: если анимация не сработала (reduced-motion, фоновая вкладка) —
  // всё равно закрываем
  useEffect(() => {
    if (!closing || !onClose) return;
    const timer = window.setTimeout(onClose, 260);
    return () => window.clearTimeout(timer);
  }, [closing, onClose]);

  useEffect(() => {
    if (!onClose) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') dismiss();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [dismiss, onClose]);

  const onAnimationEnd = useCallback(() => {
    if (closing) onClose?.();
  }, [closing, onClose]);

  return { closing, dismiss, onAnimationEnd };
}
