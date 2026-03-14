import { useState, useEffect } from "react";
import { Keyboard, X } from "lucide-react";

// ─── Shortcut definitions ──────────────────────────────────────────────────────

const SHORTCUTS = [
  {
    group: "Navigation",
    items: [
      { keys: ["⌘", "K"], desc: "Open command palette" },
      { keys: ["↑", "↓"], desc: "Navigate palette results" },
      { keys: ["↵"], desc: "Open selected result" },
      { keys: ["Esc"], desc: "Close palette / modal" },
      { keys: ["?"], desc: "Toggle this shortcuts overlay" },
    ],
  },
  {
    group: "Sidebar",
    items: [
      { keys: ["⌘", "B"], desc: "Collapse / expand sidebar" },
    ],
  },
  {
    group: "Pages — Quick Jump",
    items: [
      { keys: ["G", "D"], desc: "Go to Deal Registry" },
      { keys: ["G", "H"], desc: "Go to Health Check" },
      { keys: ["G", "P"], desc: "Go to Portfolio" },
      { keys: ["G", "S"], desc: "Go to Scenario Runner" },
      { keys: ["G", "A"], desc: "Go to Audit Log" },
    ],
  },
  {
    group: "Results",
    items: [
      { keys: ["⌘", "P"], desc: "Print current page" },
      { keys: ["⌘", "E"], desc: "Export results (when available)" },
    ],
  },
];

// ─── Kbd chip ─────────────────────────────────────────────────────────────────

function Kbd({ k }: { k: string }) {
  return (
    <kbd className="inline-flex items-center justify-center min-w-[24px] h-6 px-1.5 rounded border border-gray-200 bg-gray-50 text-xs font-mono text-gray-600 shadow-sm">
      {k}
    </kbd>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

interface Props {
  onSidebarToggle?: () => void;
}

export function KeyboardShortcuts({ onSidebarToggle }: Props) {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      const editing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

      // ? — toggle overlay
      if (!editing && e.key === "?" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setOpen((v) => !v);
      }

      // Esc — close
      if (e.key === "Escape") setOpen(false);

      // ⌘B — sidebar toggle
      if ((e.metaKey || e.ctrlKey) && e.key === "b") {
        e.preventDefault();
        onSidebarToggle?.();
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onSidebarToggle]);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="p-1.5 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors"
        title="Keyboard shortcuts (?)"
      >
        <Keyboard size={15} />
      </button>
    );
  }

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/30 z-50"
        onClick={() => setOpen(false)}
      />

      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-6 pointer-events-none">
        <div className="pointer-events-auto bg-white rounded-2xl shadow-2xl border border-gray-100 w-full max-w-lg overflow-hidden">
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
            <div className="flex items-center gap-2">
              <Keyboard size={16} className="text-gray-500" />
              <p className="text-sm font-semibold text-gray-900">Keyboard Shortcuts</p>
            </div>
            <button
              onClick={() => setOpen(false)}
              className="p-1 rounded text-gray-400 hover:text-gray-700"
            >
              <X size={15} />
            </button>
          </div>

          {/* Shortcut groups */}
          <div className="px-5 py-4 space-y-5 max-h-[70vh] overflow-y-auto">
            {SHORTCUTS.map(({ group, items }) => (
              <div key={group}>
                <p className="text-xs font-semibold uppercase tracking-wider text-gray-400 mb-2">
                  {group}
                </p>
                <div className="space-y-2">
                  {items.map(({ keys, desc }) => (
                    <div key={desc} className="flex items-center justify-between">
                      <span className="text-sm text-gray-700">{desc}</span>
                      <div className="flex items-center gap-1">
                        {keys.map((k, i) => (
                          <span key={i} className="flex items-center gap-0.5">
                            <Kbd k={k} />
                            {i < keys.length - 1 && (
                              <span className="text-xs text-gray-300 mx-0.5">+</span>
                            )}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-gray-100 text-xs text-gray-400 text-center">
            Press <Kbd k="?" /> again or <Kbd k="Esc" /> to close
          </div>
        </div>
      </div>
    </>
  );
}
