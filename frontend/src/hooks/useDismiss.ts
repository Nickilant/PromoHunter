import { useCallback, useEffect, useId, useState } from 'react';

/**
 * Плавное закрытие оверлеев: вместо мгновенного анмаунта включаем класс
 * `closing`, а реальное закрытие делаем по окончании анимации.
 * Возвращает флаг для класса и обёрнутый обработчик закрытия.
 */

/** Стопка открытых оверлеев: Escape закрывает только верхний. */
const stack: string[] = [];

export function useDismiss(onClose?: () => void) {
  const [closing, setClosing] = useState(false);
  const id = useId();

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
    stack.push(id);
    const handler = (e: KeyboardEvent) => {
      // Из карточки точки открывается отметка наличия: без этой проверки
      // один Escape закрывал бы обе
      if (e.key === 'Escape' && stack[stack.length - 1] === id) dismiss();
    };
    document.addEventListener('keydown', handler);
    return () => {
      document.removeEventListener('keydown', handler);
      const at = stack.lastIndexOf(id);
      if (at !== -1) stack.splice(at, 1);
    };
  }, [dismiss, onClose, id]);

  const onAnimationEnd = useCallback(
    (e?: { target: EventTarget | null; currentTarget: EventTarget | null }) => {
      // Анимации вложенных элементов всплывают сюда же — закрываем только по
      // собственной анимации оверлея, иначе он схлопнется раньше времени
      if (e && e.target !== e.currentTarget) return;
      if (closing) onClose?.();
    },
    [closing, onClose],
  );

  return { closing, dismiss, onAnimationEnd };
}
