"use client";
import { useState, useEffect, useCallback } from "react";
import { useLocale } from "next-intl";
import { adminApi } from "@/lib/api";

const API = process.env.NEXT_PUBLIC_API_URL || "https://api.ekklesia.gr";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  ANNOUNCED: ["ACTIVE"], ACTIVE: ["WINDOW_24H"],
  WINDOW_24H: ["PARLIAMENT_VOTED"], PARLIAMENT_VOTED: ["OPEN_END"],
};

type Tab = "overview" | "scraper" | "ollama" | "bills" | "transition" | "logs";

/* eslint-disable @typescript-eslint/no-explicit-any */

export default function AdminPage() {
  const locale = useLocale();
  const [adminKey, setAdminKey] = useState("");
  const [auth, setAuth] = useState(false);
  const [dashboard, setDash] = useState<any>(null);
  const [bills, setBills] = useState<any[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [scraperJobs, setScraperJobs] = useState<any>(null);
  const [healStatus, setHealStatus] = useState<any>(null);
  const [logAnalysis, setLogAnalysis] = useState<string>("");
  const [logLoading, setLogLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("overview");

  const el = (a: string, b: string) => locale === "el" ? a : b;

  const fetchAll = useCallback(async () => {
    if (!auth || !adminKey) return;
    try {
      const [d, b, s] = await Promise.all([
        adminApi.dashboard(adminKey),
        adminApi.bills(adminKey),
        adminApi.stats(adminKey),
      ]);
      setDash(d); setBills(b.data || []); setStats(s);
    } catch { /* silent refresh */ }
    // Scraper jobs (no auth needed)
    try {
      const r = await fetch(`${API}/api/v1/scraper/jobs`);
      if (r.ok) setScraperJobs(await r.json());
    } catch { /* */ }
    // Heal status
    try {
      const r = await fetch(`${API}/api/v1/admin/scraper/heal-status?admin_key=${adminKey}`, { method: "POST" });
      if (r.ok) setHealStatus(await r.json());
    } catch { /* */ }
  }, [auth, adminKey]);

  // Auto-refresh every 30s
  useEffect(() => {
    if (!auth) return;
    fetchAll();
    const iv = setInterval(fetchAll, 30000);
    return () => clearInterval(iv);
  }, [auth, fetchAll]);

  async function handleLogin() {
    setLoading(true); setError(null);
    try {
      const d = await adminApi.dashboard(adminKey);
      if (d.detail) { setError(d.detail); return; }
      setDash(d); setAuth(true);
    } catch { setError("Connection failed"); }
    finally { setLoading(false); }
  }

  async function handleReview(billId: string, approved: boolean) {
    await adminApi.reviewBill(adminKey, billId, approved);
    fetchAll();
  }

  async function handleTransition(billId: string, newStatus: string) {
    await adminApi.transition(adminKey, billId, newStatus);
    fetchAll();
  }

  async function explainLogs() {
    setLogLoading(true);
    try {
      const r = await fetch(`${API}/api/v1/admin/logs/explain?admin_key=${adminKey}&lines=30`, { method: "POST" });
      if (r.ok) {
        const d = await r.json();
        setLogAnalysis(d.analysis || "No analysis available");
      }
    } catch { setLogAnalysis("Failed to analyze logs"); }
    finally { setLogLoading(false); }
  }

  // Login screen
  if (!auth) return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="w-full max-w-sm p-8 bg-white rounded-2xl border border-gray-200 shadow-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-2">Dev Control Panel</h1>
        <p className="text-gray-500 text-sm mb-6">ekklesia.gr — Admin</p>
        <input type="password" placeholder="Admin Key" value={adminKey}
          onChange={e => setAdminKey(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleLogin()}
          className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl mb-4 font-mono text-sm text-gray-900 focus:border-blue-500 outline-none" />
        {error && <p className="text-red-600 text-sm mb-3">{error}</p>}
        <button onClick={handleLogin} disabled={loading || !adminKey}
          className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 rounded-xl font-bold transition-colors">
          {loading ? "..." : "Login"}
        </button>
      </div>
    </main>
  );

  const TABS: { key: Tab; label: string }[] = [
    { key: "overview", label: el("Επισκόπηση", "Overview") },
    { key: "scraper", label: "Scraper" },
    { key: "ollama", label: "Ollama" },
    { key: "bills", label: "Bills" },
    { key: "transition", label: el("Μεταβάσεις", "Transitions") },
    { key: "logs", label: "Logs" },
  ];

  return (
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-lg font-bold text-gray-900">Dev Control Panel</h1>
            <p className="text-xs text-gray-400">Auto-refresh 30s</p>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchAll} className="text-xs px-3 py-1 bg-blue-100 text-blue-700 rounded-lg hover:bg-blue-200 font-semibold">Refresh</button>
            <button onClick={() => setAuth(false)} className="text-xs px-3 py-1 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200">Logout</button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-6 flex-wrap">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${
                tab === t.key ? "bg-blue-600 text-white" : "bg-white text-gray-500 border border-gray-200 hover:text-gray-900"
              }`}>
              {t.label}
            </button>
          ))}
        </div>

        {/* ── OVERVIEW ── */}
        {tab === "overview" && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
              {[
                { label: "Bills", val: dashboard?.overview?.total_bills, color: "text-blue-600" },
                { label: el("Ψήφοι", "Votes"), val: stats?.votes?.total, color: "text-green-600" },
                { label: "Unreviewed", val: dashboard?.overview?.unreviewed_ai, color: "text-yellow-600" },
                { label: el("Ενεργά", "Active"), val: dashboard?.bills_by_status?.ACTIVE || 0, color: "text-green-600" },
              ].map(s => (
                <div key={s.label} className="bg-white rounded-xl p-4 border border-gray-200 text-center">
                  <div className={`text-2xl font-black ${s.color}`}>{s.val ?? "—"}</div>
                  <div className="text-xs text-gray-500 mt-1">{s.label}</div>
                </div>
              ))}
            </div>

            {/* Module list */}
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 className="font-bold text-sm text-gray-700 mb-3">Modules (22)</h3>
              <div className="grid grid-cols-2 gap-1">
                {(dashboard?.modules || []).slice(0, 22).map((m: string, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-gray-600 py-1">
                    <span className="w-2 h-2 bg-green-500 rounded-full flex-shrink-0" />
                    {m}
                  </div>
                ))}
              </div>
            </div>
          </>
        )}

        {/* ── SCRAPER ── */}
        {tab === "scraper" && (
          <div className="space-y-4">
            <h3 className="font-bold text-gray-900">Scraper Jobs</h3>
            {scraperJobs?.jobs ? (
              <div className="space-y-3">
                {Object.entries(scraperJobs.jobs).map(([name, job]: [string, any]) => {
                  const isError = job.error_count >= 3;
                  const isOk = job.last_success && !isError;
                  return (
                    <div key={name} className={`bg-white rounded-xl p-4 border ${isError ? "border-red-300 bg-red-50" : isOk ? "border-green-200" : "border-gray-200"}`}>
                      <div className="flex justify-between items-center mb-2">
                        <div className="flex items-center gap-2">
                          <span className={`w-2.5 h-2.5 rounded-full ${isError ? "bg-red-500" : isOk ? "bg-green-500" : "bg-yellow-500"}`} />
                          <span className="font-bold text-sm text-gray-900">{name}</span>
                        </div>
                        <span className="text-xs text-gray-400">errors: {job.error_count || 0}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                        <div>Last run: {job.last_run ? new Date(job.last_run).toLocaleString() : "—"}</div>
                        <div>Last OK: {job.last_success ? new Date(job.last_success).toLocaleString() : "—"}</div>
                      </div>
                      {job.last_error && (
                        <div className="mt-2 text-xs text-red-600 bg-red-50 rounded p-2 font-mono truncate">{job.last_error}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="text-gray-400 text-sm">Loading scraper status...</div>
            )}

            {/* Healed selectors */}
            {healStatus && (
              <div className="bg-white rounded-xl p-4 border border-gray-200 mt-4">
                <h4 className="font-bold text-sm text-gray-700 mb-2">
                  Auto-Healing: {healStatus.ollama_available ? "Ollama OK" : "Ollama offline"}
                </h4>
                {healStatus.healed_selectors?.length > 0 ? (
                  <div className="space-y-1">
                    {healStatus.healed_selectors.map((s: any, i: number) => (
                      <div key={i} className="text-xs text-gray-600 font-mono">{s.key}: {s.selector} (TTL: {s.ttl_hours}h)</div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-gray-400">No healed selectors (all scrapers healthy)</p>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── OLLAMA ── */}
        {tab === "ollama" && (
          <div className="space-y-4">
            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h3 className="font-bold text-gray-900 mb-3">Ollama Status</h3>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">Model</div>
                  <div className="font-bold text-sm text-gray-900">llama3.2:3b</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">Status</div>
                  <div className={`font-bold text-sm ${healStatus?.ollama_available ? "text-green-600" : "text-red-600"}`}>
                    {healStatus?.ollama_available ? "Online" : "Offline"}
                  </div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">Memory Limit</div>
                  <div className="font-bold text-sm text-gray-900">5 GB</div>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <div className="text-xs text-gray-500 mb-1">Rate Limit</div>
                  <div className="font-bold text-sm text-gray-900">5 req/min/IP</div>
                </div>
              </div>
            </div>

            <div className="bg-white rounded-xl p-4 border border-gray-200">
              <h4 className="font-bold text-sm text-gray-700 mb-2">Endpoints</h4>
              <div className="space-y-1 text-xs text-gray-600 font-mono">
                <div>POST /api/v1/agent/ask — RAG citizen Q&A</div>
                <div>GET /api/v1/bills/[id]/summary — Bill summary</div>
                <div>POST /api/v1/admin/logs/explain — Log analysis</div>
                <div>POST /api/v1/admin/scraper/heal-status — Healer status</div>
              </div>
            </div>
          </div>
        )}

        {/* ── BILLS ── */}
        {tab === "bills" && (
          <div className="space-y-3">
            {bills.map((b: any) => (
              <div key={b.id} className="bg-white rounded-xl p-4 border border-gray-200">
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm text-gray-900 truncate">{b.title_el}</p>
                    <div className="flex gap-2 mt-1">
                      <span className="text-xs text-gray-400">{b.status}</span>
                      <span className={`text-xs ${b.ai_summary_reviewed ? "text-green-600" : "text-yellow-600"}`}>
                        {b.ai_summary_reviewed ? "Reviewed" : "Unreviewed"}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2 ml-2">
                    {!b.ai_summary_reviewed && (
                      <>
                        <button onClick={() => handleReview(b.id, true)} className="px-2 py-1 bg-green-100 hover:bg-green-200 text-green-700 rounded text-xs font-bold">✓</button>
                        <button onClick={() => handleReview(b.id, false)} className="px-2 py-1 bg-red-100 hover:bg-red-200 text-red-700 rounded text-xs font-bold">✗</button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── TRANSITIONS ── */}
        {tab === "transition" && (
          <div className="space-y-3">
            {bills.filter((b: any) => STATUS_TRANSITIONS[b.status]?.length > 0).map((b: any) => (
              <div key={b.id} className="bg-white rounded-xl p-4 border border-gray-200">
                <p className="font-semibold text-sm text-gray-900 mb-2 truncate">{b.title_el}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">{b.status}</span>
                  <span className="text-gray-400">→</span>
                  {(STATUS_TRANSITIONS[b.status] || []).map((next: string) => (
                    <button key={next} onClick={() => handleTransition(b.id, next)}
                      className="text-xs bg-blue-100 hover:bg-blue-200 text-blue-700 px-3 py-1 rounded-lg font-bold transition-colors">
                      {next}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── LOGS ── */}
        {tab === "logs" && (
          <div className="space-y-4">
            <div className="flex gap-2">
              <button onClick={explainLogs} disabled={logLoading}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-bold hover:bg-blue-700 disabled:opacity-50">
                {logLoading ? "Analyzing..." : "Ollama: Explain Logs"}
              </button>
            </div>
            {logAnalysis && (
              <div className="bg-white rounded-xl p-4 border border-gray-200">
                <h4 className="font-bold text-sm text-gray-700 mb-2">Ollama Log Analysis</h4>
                <pre className="text-xs text-gray-600 whitespace-pre-wrap leading-relaxed">{logAnalysis}</pre>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
