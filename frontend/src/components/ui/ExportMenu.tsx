import { useState, useRef, useEffect } from "react";
import { Download, FileText, Braces } from "lucide-react";
import { downloadCSV, downloadJSON, flattenForCSV } from "../../lib/export";

interface ExportMenuProps {
  /** Label used in filename, e.g. "health-check" */
  label: string;
  /** Raw data to export as JSON */
  data: unknown;
  /** Optional array of flat row objects for CSV; if omitted, data is flattened */
  csvRows?: Record<string, unknown>[];
}

export function ExportMenu({ label, data, csvRows }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const ts = new Date().toISOString().slice(0, 16).replace("T", "_").replace(":", "-");
  const base = `${label}_${ts}`;

  useEffect(() => {
    if (!open) return;
    function h(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [open]);

  function handleCSV() {
    const rows = csvRows ?? (
      Array.isArray(data)
        ? (data as Record<string, unknown>[]).map((r) => flattenForCSV(r))
        : [flattenForCSV(data as Record<string, unknown>)]
    );
    downloadCSV(rows, `${base}.csv`);
    setOpen(false);
  }

  function handleJSON() {
    downloadJSON(data, `${base}.json`);
    setOpen(false);
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-gray-200 text-xs font-medium text-gray-600 hover:bg-gray-50 transition-colors"
        title="Export results"
      >
        <Download size={12} />
        Export
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-lg shadow-lg border border-gray-100 overflow-hidden z-20">
          <button
            onClick={handleCSV}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
          >
            <FileText size={12} className="text-gray-400" /> CSV
          </button>
          <button
            onClick={handleJSON}
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-700 hover:bg-gray-50"
          >
            <Braces size={12} className="text-gray-400" /> JSON
          </button>
        </div>
      )}
    </div>
  );
}
