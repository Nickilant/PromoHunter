import { useEffect } from 'react';

/** Закрытие модалки по Escape. Передайте undefined, если закрывать нельзя. */
export function useEscape(onEscape?: () => void) {
  useEffect(() => {
    if (!onEscape) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onEscape();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onEscape]);
}
