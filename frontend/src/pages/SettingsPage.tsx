import { useState, useEffect } from "react";
import { SectionCard } from "../components/SectionCard";
import { Button } from "../components/ui/Button";
import { useToast } from "../components/ui/Toast";
import { client } from "../api/client";
import { Settings } from "lucide-react";

// ─── Settings schema ───────────────────────────────────────────────────────────

const DEFAULTS = {
  apiBaseUrl: "http://localhost:8000",
  monitorRefreshMs: 30000,
  maxDealsMonitor: 12,
  theme: "dark" as "dark" | "light",
  alertSoundEnabled: false,
  printOrientation: "portrait" as "portrait" | "landscape",
  defaultChannel: "internal",
};

type AppSettings = typeof DEFAULTS;

const STORAGE_KEY = "ai-deal-creator-settings";

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
  } catch { /* ignore */ }
  return { ...DEFAULTS };
}

function saveSettings(s: AppSettings) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export function SettingsPage() {
  const toast = useToast();
  const [settings, setSettings] = useState<AppSettings>(loadSettings);
  const [apiStatus, setApiStatus] = useState<"idle" | "ok" | "error">("idle");
  const [dirty, setDirty] = useState(false);

  useEffect(() => { setDirty(true); }, [settings]);

  function update<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }

  function handleSave() {
    saveSettings(settings);
    // Apply base URL to axios client
    client.defaults.baseURL = settings.apiBaseUrl;
    setDirty(false);
    toast.success("Settings saved.");
  }

  function handleReset() {
    setSettings({ ...DEFAULTS });
    saveSettings(DEFAULTS);
    client.defaults.baseURL = DEFAULTS.apiBaseUrl;
    toast.info("Settings reset to defaults.");
  }

  async function testConnection() {
    setApiStatus("idle");
    try {
      await client.get("/health", { timeout: 3000 });
      setApiStatus("ok");
      toast.success("API connection successful.");
    } catch {
      setApiStatus("error");
      toast.error("Could not reach API.");
    }
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Configure workspace preferences</p>
      </div>

      {/* API */}
      <SectionCard title="API Connection">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-500 font-medium">Backend Base URL</label>
            <div className="flex gap-2 mt-1">
              <input
                className="flex-1 border border-gray-200 rounded-md px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-gray-900"
                value={settings.apiBaseUrl}
                onChange={(e) => update("apiBaseUrl", e.target.value)}
              />
              <button
                onClick={testConnection}
                className={`px-3 py-2 rounded-md text-xs font-medium border transition-colors ${
                  apiStatus === "ok"
                    ? "border-green-300 text-green-700 bg-green-50"
                    : apiStatus === "error"
                    ? "border-red-300 text-red-700 bg-red-50"
                    : "border-gray-200 text-gray-600 hover:bg-gray-50"
                }`}
              >
                {apiStatus === "ok" ? "✓ Connected" : apiStatus === "error" ? "✗ Failed" : "Test"}
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 font-medium">Default Channel</label>
            <select
              className="mt-1 w-full border border-gray-200 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
              value={settings.defaultChannel}
              onChange={(e) => update("defaultChannel", e.target.value)}
            >
              <option value="internal">internal</option>
              <option value="external">external</option>
              <option value="investor_portal">investor_portal</option>
            </select>
          </div>
        </div>
      </SectionCard>

      {/* Monitor */}
      <SectionCard title="Live Monitor">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-500 font-medium">
              Default Refresh Interval — {settings.monitorRefreshMs / 1000}s
            </label>
            <input
              type="range"
              min={10000}
              max={120000}
              step={5000}
              value={settings.monitorRefreshMs}
              onChange={(e) => update("monitorRefreshMs", Number(e.target.value))}
              className="mt-2 w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>10s</span><span>120s</span>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 font-medium">
              Max Deals in Monitor — {settings.maxDealsMonitor}
            </label>
            <input
              type="range"
              min={4}
              max={24}
              step={2}
              value={settings.maxDealsMonitor}
              onChange={(e) => update("maxDealsMonitor", Number(e.target.value))}
              className="mt-2 w-full accent-blue-600"
            />
            <div className="flex justify-between text-xs text-gray-400 mt-1">
              <span>4</span><span>24</span>
            </div>
          </div>
        </div>
      </SectionCard>

      {/* Alerts */}
      <SectionCard title="Alerts">
        <label className="flex items-center gap-3 cursor-pointer">
          <div
            onClick={() => update("alertSoundEnabled", !settings.alertSoundEnabled)}
            className={`w-10 h-5 rounded-full transition-colors relative ${
              settings.alertSoundEnabled ? "bg-blue-500" : "bg-gray-300"
            }`}
          >
            <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${
              settings.alertSoundEnabled ? "translate-x-5" : "translate-x-0.5"
            }`} />
          </div>
          <span className="text-sm text-gray-700">Enable alert sounds</span>
        </label>
      </SectionCard>

      {/* Display */}
      <SectionCard title="Display">
        <div className="space-y-4">
          <div>
            <label className="text-xs text-gray-500 font-medium">Sidebar Theme</label>
            <div className="flex gap-3 mt-2">
              {(["dark", "light"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => update("theme", t)}
                  className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm transition-colors ${
                    settings.theme === t
                      ? "border-blue-400 bg-blue-50 text-blue-700 font-medium"
                      : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  <div className={`w-4 h-4 rounded ${t === "dark" ? "bg-gray-900" : "bg-gray-100 border border-gray-200"}`} />
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 font-medium">Print Orientation</label>
            <div className="flex gap-3 mt-2">
              {(["portrait", "landscape"] as const).map((o) => (
                <button
                  key={o}
                  onClick={() => update("printOrientation", o)}
                  className={`px-4 py-2 rounded-lg border text-sm transition-colors ${
                    settings.printOrientation === o
                      ? "border-blue-400 bg-blue-50 text-blue-700 font-medium"
                      : "border-gray-200 text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {o.charAt(0).toUpperCase() + o.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>
      </SectionCard>

      {/* About */}
      <SectionCard title="About">
        <div className="space-y-1 text-xs text-gray-500">
          <div className="flex gap-3">
            <span className="w-28 text-gray-400">Version</span>
            <span className="font-mono">Phase 45 (Phase 1 — Mock Engine)</span>
          </div>
          <div className="flex gap-3">
            <span className="w-28 text-gray-400">Backend</span>
            <span className="font-mono">{settings.apiBaseUrl}</span>
          </div>
          <div className="flex gap-3">
            <span className="w-28 text-gray-400">Frontend</span>
            <span className="font-mono">React 18 + Vite + Tailwind CSS v3</span>
          </div>
          <div className="flex gap-3">
            <span className="w-28 text-gray-400">Data</span>
            <span className="font-mono text-amber-600">Mock engine — not for investment use</span>
          </div>
        </div>
      </SectionCard>

      {/* Actions */}
      <div className="flex items-center gap-3 sticky bottom-4 bg-white border border-gray-100 shadow-lg rounded-xl px-5 py-3">
        <Settings size={14} className="text-gray-400" />
        <span className="text-xs text-gray-400 flex-1">{dirty ? "Unsaved changes" : "All changes saved"}</span>
        <Button variant="outline" onClick={handleReset}>Reset to Defaults</Button>
        <Button onClick={handleSave} disabled={!dirty}>Save Settings</Button>
      </div>
    </div>
  );
}
