"use client";
import { useState } from "react";
import { useLocale } from "next-intl";
import Link from "next/link";
import { adminApi } from "@/lib/api";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  ANNOUNCED: ["ACTIVE"], ACTIVE: ["WINDOW_24H"],
  WINDOW_24H: ["PARLIAMENT_VOTED"], PARLIAMENT_VOTED: ["OPEN_END"],
};

export default function AdminPage() {
  const locale = useLocale();
  /* eslint-disable @typescript-eslint/no-explicit-any */
  const [adminKey, setAdminKey] = useState("");
  const [auth, setAuth]         = useState(false);
  const [dashboard, setDash]    = useState<any>(null);
  const [bills, setBills]       = useState<any[]>([]);
  const [stats, setStats]       = useState<any>(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState<string | null>(null);
  const [tab, setTab]           = useState<"overview" | "bills" | "transition">("overview");

  const el = (a: string, b: string) => locale === "el" ? a : b;

  async function handleLogin() {
    setLoading(true); setError(null);
    try {
      const d = await adminApi.dashboard(adminKey);
      if (d.detail) { setError(d.detail); return; }
      setDash(d); setAuth(true);
      const [b, s] = await Promise.all([adminApi.bills(adminKey), adminApi.stats(adminKey)]);
      setBills(b.data || []); setStats(s);
    } catch { setError("Σύνδεση αποτυχία"); }
    finally { setLoading(false); }
  }

  async function handleReview(billId: string, approved: boolean) {
    await adminApi.reviewBill(adminKey, billId, approved);
    const b = await adminApi.bills(adminKey);
    setBills(b.data || []);
  }

  async function handleTransition(billId: string, newStatus: string) {
    await adminApi.transition(adminKey, billId, newStatus);
    const b = await adminApi.bills(adminKey);
    setBills(b.data || []);
  }

  if (!auth) return (
    <main className="min-h-screen bg-gray-950 text-white flex items-center justify-center">
      <div className="w-full max-w-sm p-8 bg-gray-900 rounded-2xl border border-gray-800">
        <h1 className="text-2xl font-bold mb-2">Admin Panel</h1>
        <p className="text-gray-400 text-sm mb-6">εκκλησία — Beta Admin</p>
        <input type="password" placeholder="Admin Key" value={adminKey}
          onChange={e => setAdminKey(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleLogin()}
          className="w-full p-3 bg-gray-800 border border-gray-700 rounded-xl mb-4 font-mono text-sm focus:border-blue-500 outline-none" />
        {error && <p className="text-red-400 text-sm mb-3">{error}</p>}
        <button onClick={handleLogin} disabled={loading || !adminKey}
          className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 rounded-xl font-bold transition-colors">
          {loading ? "..." : el("Σύνδεση", "Login")}
        </button>
      </div>
    </main>
  );

  return (
    <main className="min-h-screen bg-gray-950 text-white">
      <div className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-sm font-bold text-gray-300">Admin Panel</h1>
          <button onClick={() => setAuth(false)} className="text-xs text-gray-500 hover:text-white">Logout</button>
        </div>
        <div className="flex gap-2 mb-6">
          {(["overview", "bills", "transition"] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-lg text-sm font-bold transition-colors ${
                tab === t ? "bg-blue-600 text-white" : "bg-gray-800 text-gray-400 hover:text-white"
              }`}>
              {t === "overview" ? el("Επισκόπηση", "Overview") : t === "bills" ? "Bills" : el("Μεταβάσεις", "Transitions")}
            </button>
          ))}
        </div>

        {tab === "overview" && dashboard && (
          <>
            <div className="grid grid-cols-2 gap-3 mb-6">
              {[
                { label: "Bills", val: dashboard.overview?.total_bills, color: "text-blue-400" },
                { label: el("Ψήφοι", "Votes"), val: stats?.votes?.total, color: "text-green-400" },
                { label: "Unreviewed AI", val: dashboard.overview?.unreviewed_ai, color: "text-yellow-400" },
                { label: el("Ενεργά", "Active"), val: dashboard.bills_by_status?.ACTIVE || 0, color: "text-green-400" },
              ].map(s => (
                <div key={s.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800 text-center">
                  <div className={`text-2xl font-black ${s.color}`}>{s.val ?? "—"}</div>
                  <div className="text-xs text-gray-500 mt-1">{s.label}</div>
                </div>
              ))}
            </div>
          </>
        )}

        {tab === "bills" && (
          <div className="space-y-3">
            {bills.map((b: any) => (
              <div key={b.id} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold text-sm truncate">{b.title_el}</p>
                    <div className="flex gap-2 mt-1">
                      <span className="text-xs text-gray-500">{b.status}</span>
                      <span className={`text-xs ${b.ai_summary_reviewed ? "text-green-400" : "text-yellow-400"}`}>
                        {b.ai_summary_reviewed ? "Reviewed" : "Unreviewed"}
                      </span>
                    </div>
                  </div>
                  <div className="flex gap-2 ml-2">
                    {!b.ai_summary_reviewed && (
                      <>
                        <button onClick={() => handleReview(b.id, true)} className="px-2 py-1 bg-green-800 hover:bg-green-700 rounded text-xs font-bold">✓</button>
                        <button onClick={() => handleReview(b.id, false)} className="px-2 py-1 bg-red-900 hover:bg-red-800 rounded text-xs font-bold">✗</button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {tab === "transition" && (
          <div className="space-y-3">
            {bills.filter((b: any) => STATUS_TRANSITIONS[b.status]?.length > 0).map((b: any) => (
              <div key={b.id} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
                <p className="font-semibold text-sm mb-2 truncate">{b.title_el}</p>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-gray-800 px-2 py-1 rounded">{b.status}</span>
                  <span className="text-gray-600">→</span>
                  {(STATUS_TRANSITIONS[b.status] || []).map((next: string) => (
                    <button key={next} onClick={() => handleTransition(b.id, next)}
                      className="text-xs bg-blue-800 hover:bg-blue-700 px-3 py-1 rounded-lg font-bold transition-colors">
                      {next}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
