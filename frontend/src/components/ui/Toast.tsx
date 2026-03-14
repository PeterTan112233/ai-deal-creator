import {
  createContext,
  useContext,
  useState,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from "lucide-react";

// ─── Types ────────────────────────────────────────────────────────────────────

export type ToastVariant = "success" | "error" | "info" | "warning";

export interface NotificationItem {
  id: number;
  message: string;
  variant: ToastVariant;
  timestamp: Date;
  read: boolean;
}

interface ToastItem {
  id: number;
  message: string;
  variant: ToastVariant;
}

interface ToastContextValue {
  addToast: (message: string, variant: ToastVariant) => void;
  notifications: NotificationItem[];
  unreadCount: number;
  markAllRead: () => void;
  clearAll: () => void;
  dismissNotification: (id: number) => void;
}

// ─── Context ──────────────────────────────────────────────────────────────────

const ToastContext = createContext<ToastContextValue>({
  addToast: () => {},
  notifications: [],
  unreadCount: 0,
  markAllRead: () => {},
  clearAll: () => {},
  dismissNotification: () => {},
});

// ─── Styles ───────────────────────────────────────────────────────────────────

export const VARIANT_STYLES: Record<ToastVariant, { container: string; icon: string; dot: string }> = {
  success: {
    container: "bg-emerald-50 border-emerald-200 text-emerald-800",
    icon: "text-emerald-500",
    dot: "bg-emerald-500",
  },
  error: {
    container: "bg-red-50 border-red-200 text-red-800",
    icon: "text-red-500",
    dot: "bg-red-500",
  },
  warning: {
    container: "bg-amber-50 border-amber-200 text-amber-800",
    icon: "text-amber-500",
    dot: "bg-amber-500",
  },
  info: {
    container: "bg-blue-50 border-blue-200 text-blue-800",
    icon: "text-blue-500",
    dot: "bg-blue-500",
  },
};

export const ICONS = {
  success: CheckCircle,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
} as const;

// ─── Provider ─────────────────────────────────────────────────────────────────

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const idRef = useRef(0);

  const addToast = useCallback((message: string, variant: ToastVariant = "info") => {
    const id = ++idRef.current;
    const item: NotificationItem = { id, message, variant, timestamp: new Date(), read: false };

    // Add to transient toast stack
    setToasts((prev) => [...prev, { id, message, variant }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);

    // Add to persistent history (cap at 100)
    setNotifications((prev) => [item, ...prev].slice(0, 100));
  }, []);

  const dismiss = (id: number) =>
    setToasts((prev) => prev.filter((t) => t.id !== id));

  const markAllRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearAll = useCallback(() => setNotifications([]), []);

  const dismissNotification = useCallback((id: number) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <ToastContext.Provider value={{ addToast, notifications, unreadCount, markAllRead, clearAll, dismissNotification }}>
      {children}
      {/* Toast stack — bottom-right */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 w-80 pointer-events-none">
        {toasts.map((t) => {
          const styles = VARIANT_STYLES[t.variant];
          const Icon = ICONS[t.variant];
          return (
            <div
              key={t.id}
              className={`flex items-start gap-3 px-4 py-3 rounded-lg border shadow-lg pointer-events-auto ${styles.container}`}
            >
              <Icon size={16} className={`mt-0.5 shrink-0 ${styles.icon}`} />
              <p className="flex-1 text-sm font-medium leading-snug">{t.message}</p>
              <button
                onClick={() => dismiss(t.id)}
                className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

export function useToast() {
  const { addToast } = useContext(ToastContext);
  return {
    success: (msg: string) => addToast(msg, "success"),
    error: (msg: string) => addToast(msg, "error"),
    info: (msg: string) => addToast(msg, "info"),
    warning: (msg: string) => addToast(msg, "warning"),
  };
}

export function useNotifications() {
  const { notifications, unreadCount, markAllRead, clearAll, dismissNotification } = useContext(ToastContext);
  return { notifications, unreadCount, markAllRead, clearAll, dismissNotification };
}
