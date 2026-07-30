import { useEffect, useRef, useState } from 'react';

/**
 * Локальный отсчёт от значения, которое пришло с сервера.
 *
 * Сервер отдаёт «сколько осталось», а не момент окончания: шкала может стоять
 * (точка закрыта, перемирие), поэтому абсолютное время окончания смысла не
 * имеет. Тикаем сами, пока `running`, и перезапускаемся, когда придёт новое
 * значение.
 */
export function useCountdown(seconds: number | null, running = true): number | null {
  const [left, setLeft] = useState<number | null>(seconds);
  const base = useRef<{ value: number; at: number } | null>(null);

  useEffect(() => {
    setLeft(seconds);
    base.current = seconds === null ? null : { value: seconds, at: Date.now() };
  }, [seconds]);

  useEffect(() => {
    if (!running || seconds === null) return;
    const tick = () => {
      const anchor = base.current;
      if (!anchor) return;
      const passed = (Date.now() - anchor.at) / 1000;
      setLeft(Math.max(0, anchor.value - passed));
    };
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [running, seconds]);

  return left;
}
