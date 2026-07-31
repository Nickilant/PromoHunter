/**
 * Тонкая обёртка над Telegram WebApp.
 *
 * Зачем она нужна: SDK объявляет все методы независимо от версии клиента, а
 * при вызове неподдерживаемого бросает `WebAppMethodUnsupported`. Поэтому
 * привычная проверка `webApp.method?.()` ничего не гарантирует — метод есть,
 * но падает. Один такой вызов в размонтировании компонента уносил всё
 * приложение в белый экран.
 *
 * Правило: любой вызов Telegram идёт через `safe`, а методы, появившиеся
 * позже 6.0, дополнительно проверяются `supports`.
 */

export function webApp(): TelegramWebApp | null {
  return window.Telegram?.WebApp ?? null;
}

/** Открыто ли приложение из Telegram (а не в обычном браузере). */
export function inTelegram(): boolean {
  const app = webApp();
  return !!app?.initData;
}

/** Версия Bot API у клиента не ниже указанной. */
export function supports(version: string): boolean {
  const app = webApp();
  if (!app) return false;
  if (app.isVersionAtLeast) return safe(() => app.isVersionAtLeast!(version)) === true;
  // Совсем древний SDK без isVersionAtLeast — считаем, что не умеет ничего
  return false;
}

/**
 * Вызвать метод Telegram, проглотив отказ клиента.
 *
 * Возвращает undefined, если метода нет или клиент его не поддерживает:
 * для нас это всегда необязательная возможность, а не ошибка сценария.
 */
export function safe<T>(fn: () => T): T | undefined {
  try {
    return fn();
  } catch (error) {
    // Старый клиент — это норма, а не сбой: пишем в консоль и живём дальше
    console.info('Telegram WebApp отказал в вызове:', error);
    return undefined;
  }
}

/**
 * То же, но с признаком успеха — для методов, которые ничего не возвращают.
 * По `safe` их не отличить: там undefined и при отказе, и при удачном вызове.
 */
export function attempt(fn: () => void): boolean {
  try {
    fn();
    return true;
  } catch (error) {
    console.info('Telegram WebApp отказал в вызове:', error);
    return false;
  }
}
