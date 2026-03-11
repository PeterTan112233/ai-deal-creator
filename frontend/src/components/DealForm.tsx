import { useState } from "react";
import { Button } from "./ui/Button";
import { Input } from "./ui/Input";
import { Select } from "./ui/Select";
import { Plus, Trash2 } from "lucide-react";

interface TrancheRow {
  name: string;
  rating: string;
  size_pct: string;
  coupon: string;
}

interface FormState {
  name: string;
  issuer: string;
  region: string;
  asset_class: string;
  portfolio_size: string;
  wal: string;
  warf: string;
  was: string;
  diversity_score: string;
  ccc_bucket: string;
  tranches: TrancheRow[];
}

const DEFAULT_TRANCHES: TrancheRow[] = [
  { name: "Class A", rating: "AAA", size_pct: "0.62", coupon: "0.069" },
  { name: "Class B", rating: "AA",  size_pct: "0.11", coupon: "0.074" },
  { name: "Class C", rating: "A",   size_pct: "0.07", coupon: "0.082" },
  { name: "Class D", rating: "BBB", size_pct: "0.05", coupon: "0.094" },
  { name: "Class E", rating: "BB",  size_pct: "0.04", coupon: "0.126" },
  { name: "Equity",  rating: "NR",  size_pct: "0.11", coupon: "0.0"   },
];

const EMPTY_STATE: FormState = {
  name: "", issuer: "", region: "US",
  asset_class: "BSL", portfolio_size: "500000000",
  wal: "5.1", warf: "2850", was: "0.0450",
  diversity_score: "75", ccc_bucket: "0.042",
  tranches: DEFAULT_TRANCHES,
};

function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function formToInput(f: FormState): Record<string, unknown> {
  const id = (slug(f.name) || "deal") + "-" + Math.random().toString(36).slice(2, 6);
  return {
    deal_id: id,
    name: f.name,
    issuer: f.issuer,
    region: f.region || null,
    collateral: {
      pool_id: "pool-" + id,
      asset_class: f.asset_class,
      portfolio_size: parseFloat(f.portfolio_size),
      wal: parseFloat(f.wal),
      warf: parseFloat(f.warf) || null,
      was: parseFloat(f.was),
      diversity_score: parseFloat(f.diversity_score),
      ccc_bucket: parseFloat(f.ccc_bucket),
    },
    liabilities: f.tranches.map((t, i) => ({
      tranche_id: `tr-${i + 1}`,
      name: t.name,
      rating: t.rating,
      seniority: i + 1,
      size_pct: parseFloat(t.size_pct) || 0,
      coupon: parseFloat(t.coupon) || 0,
    })),
  };
}

function validate(f: FormState): string | null {
  if (!f.name.trim()) return "Deal name is required.";
  if (!f.issuer.trim()) return "Issuer is required.";
  if (!parseFloat(f.portfolio_size)) return "Portfolio size must be a positive number.";
  if (!parseFloat(f.was)) return "WAS must be a positive number (e.g. 0.045 for 450bps).";
  if (f.tranches.length === 0) return "At least one tranche is required.";
  const totalPct = f.tranches.reduce((s, t) => s + (parseFloat(t.size_pct) || 0), 0);
  if (Math.abs(totalPct - 1) > 0.01) return `Tranche size_pct must sum to 1.0 (currently ${totalPct.toFixed(3)}).`;
  return null;
}

interface Props {
  onSubmit: (dealInput: Record<string, unknown>) => void;
  isSubmitting?: boolean;
  submitLabel?: string;
}

export function DealForm({ onSubmit, isSubmitting, submitLabel = "Register Deal" }: Props) {
  const [f, setF] = useState<FormState>(EMPTY_STATE);
  const [error, setError] = useState<string | null>(null);

  function set(key: keyof Omit<FormState, "tranches">, val: string) {
    setF((prev) => ({ ...prev, [key]: val }));
  }

  function setTranche(i: number, key: keyof TrancheRow, val: string) {
    setF((prev) => {
      const t = [...prev.tranches];
      t[i] = { ...t[i], [key]: val };
      return { ...prev, tranches: t };
    });
  }

  function addTranche() {
    setF((prev) => ({
      ...prev,
      tranches: [...prev.tranches, { name: "", rating: "BBB", size_pct: "0.05", coupon: "0.09" }],
    }));
  }

  function removeTranche(i: number) {
    setF((prev) => ({ ...prev, tranches: prev.tranches.filter((_, j) => j !== i) }));
  }

  function handleSubmit() {
    setError(null);
    const err = validate(f);
    if (err) { setError(err); return; }
    onSubmit(formToInput(f));
  }

  const totalPct = f.tranches.reduce((s, t) => s + (parseFloat(t.size_pct) || 0), 0);
  const pctOk = Math.abs(totalPct - 1) <= 0.01;

  return (
    <div className="space-y-6">

      {/* Deal Info */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
          Deal Info
        </h4>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Deal Name *</label>
            <Input value={f.name} onChange={(e) => set("name", e.target.value)} placeholder="Apex CLO 2024-1" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Issuer *</label>
            <Input value={f.issuer} onChange={(e) => set("issuer", e.target.value)} placeholder="Apex Capital Management" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Region</label>
            <Select value={f.region} onChange={(e) => set("region", e.target.value)}>
              <option value="US">US</option>
              <option value="EU">EU</option>
              <option value="APAC">APAC</option>
            </Select>
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Asset Class</label>
            <Select value={f.asset_class} onChange={(e) => set("asset_class", e.target.value)}>
              <option value="BSL">BSL — Broadly Syndicated Loans</option>
              <option value="MM">MM — Middle Market</option>
              <option value="CRE">CRE — Commercial Real Estate</option>
            </Select>
          </div>
        </div>
      </div>

      {/* Collateral */}
      <div>
        <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-3">
          Pool / Collateral
        </h4>
        <div className="grid grid-cols-3 gap-3">
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Portfolio Size ($) *</label>
            <Input value={f.portfolio_size} onChange={(e) => set("portfolio_size", e.target.value)} placeholder="500000000" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">WAL (years)</label>
            <Input value={f.wal} onChange={(e) => set("wal", e.target.value)} placeholder="5.1" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">WAS (decimal) *</label>
            <Input value={f.was} onChange={(e) => set("was", e.target.value)} placeholder="0.0450 = 450bps" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">WARF</label>
            <Input value={f.warf} onChange={(e) => set("warf", e.target.value)} placeholder="2850" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">Diversity Score</label>
            <Input value={f.diversity_score} onChange={(e) => set("diversity_score", e.target.value)} placeholder="75" />
          </div>
          <div>
            <label className="text-xs text-gray-600 mb-1 block">CCC Bucket (decimal)</label>
            <Input value={f.ccc_bucket} onChange={(e) => set("ccc_bucket", e.target.value)} placeholder="0.042 = 4.2%" />
          </div>
        </div>
      </div>

      {/* Tranches */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Tranches
          </h4>
          <span className={`text-xs font-mono ${pctOk ? "text-green-600" : "text-red-500"}`}>
            Σ size_pct = {totalPct.toFixed(3)} {pctOk ? "✓" : "(must = 1.000)"}
          </span>
        </div>
        <div className="border border-gray-100 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr className="text-xs uppercase text-gray-500">
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Rating</th>
                <th className="px-3 py-2 text-left">Size %</th>
                <th className="px-3 py-2 text-left">Coupon (all-in)</th>
                <th className="px-3 py-2 w-8" />
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {f.tranches.map((t, i) => (
                <tr key={i}>
                  <td className="px-3 py-1.5">
                    <Input
                      value={t.name}
                      onChange={(e) => setTranche(i, "name", e.target.value)}
                      className="h-8 text-xs"
                      placeholder="Class A"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    <Select
                      value={t.rating}
                      onChange={(e) => setTranche(i, "rating", e.target.value)}
                      className="h-8 text-xs"
                    >
                      {["AAA", "AA", "A", "BBB", "BB", "B", "NR"].map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                    </Select>
                  </td>
                  <td className="px-3 py-1.5">
                    <Input
                      value={t.size_pct}
                      onChange={(e) => setTranche(i, "size_pct", e.target.value)}
                      className="h-8 text-xs font-mono"
                      placeholder="0.62"
                    />
                  </td>
                  <td className="px-3 py-1.5">
                    <Input
                      value={t.coupon}
                      onChange={(e) => setTranche(i, "coupon", e.target.value)}
                      className="h-8 text-xs font-mono"
                      placeholder="0.069"
                    />
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    <button
                      onClick={() => removeTranche(i)}
                      className="text-gray-300 hover:text-red-500 transition-colors"
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-3 py-2 bg-gray-50 border-t border-gray-100">
            <button
              onClick={addTranche}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900"
            >
              <Plus size={12} /> Add tranche
            </button>
          </div>
        </div>
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      <Button onClick={handleSubmit} disabled={isSubmitting}>
        {isSubmitting ? "Registering…" : submitLabel}
      </Button>
    </div>
  );
}
