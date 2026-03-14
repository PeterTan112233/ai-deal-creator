import { Printer } from "lucide-react";

interface Props {
  label?: string;
}

export function PrintButton({ label = "Print Report" }: Props) {
  return (
    <button
      onClick={() => window.print()}
      className="no-print flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-gray-200 text-xs text-gray-600 hover:bg-gray-50 hover:border-gray-400 transition-colors"
    >
      <Printer size={13} />
      {label}
    </button>
  );
}
