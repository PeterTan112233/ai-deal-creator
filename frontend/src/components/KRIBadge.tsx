import { cn } from "../lib/utils";

interface KRIBadgeProps {
  status: "ok" | "warn" | "critical" | string;
  label?: string;
}

export function KRIBadge({ status, label }: KRIBadgeProps) {
  const normalized = status?.toLowerCase();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide",
        normalized === "ok" && "bg-green-100 text-green-800",
        normalized === "warn" || normalized === "warning"
          ? "bg-yellow-100 text-yellow-800"
          : "",
        normalized === "critical" && "bg-red-100 text-red-800",
        !["ok", "warn", "warning", "critical"].includes(normalized) &&
          "bg-gray-100 text-gray-700"
      )}
    >
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          normalized === "ok" && "bg-green-500",
          normalized === "warn" || normalized === "warning" ? "bg-yellow-500" : "",
          normalized === "critical" && "bg-red-500",
          !["ok", "warn", "warning", "critical"].includes(normalized) && "bg-gray-400"
        )}
      />
      {label ?? status}
    </span>
  );
}
