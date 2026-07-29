import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useRef,
  useState,
} from 'react';

const ToastContext = createContext<(message: string) => void>(() => {});

const VISIBLE_MS = 2500;
const LEAVE_MS = 200;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [message, setMessage] = useState<string | null>(null);
  const [leaving, setLeaving] = useState(false);
  const timers = useRef<number[]>([]);

  const show = useCallback((text: string) => {
    timers.current.forEach(window.clearTimeout);
    timers.current = [];
    setLeaving(false);
    setMessage(text);
    // Сначала уводим анимацией, потом снимаем с экрана
    timers.current.push(
      window.setTimeout(() => setLeaving(true), VISIBLE_MS),
      window.setTimeout(() => setMessage(null), VISIBLE_MS + LEAVE_MS),
    );
  }, []);

  return (
    <ToastContext.Provider value={show}>
      {children}
      {message && (
        <div className={`toast${leaving ? ' leaving' : ''}`} role="status" aria-live="polite">
          {message}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
