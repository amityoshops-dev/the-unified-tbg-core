import { useState, useEffect } from 'react';
import { ShieldCheck, Database, ArrowUpRight, ArrowDownLeft, RefreshCw, Send, SlidersHorizontal } from 'lucide-react';

export default function App() {
  const [telemetry, setTelemetry] = useState<any>({
    total_liquidity: '₹ 4,32,00,000.00',
    balances: {
      ESCROW_RETENTION_70: '₹ 1,05,00,000.00',
      BUILDER_CURRENT_30: '₹ 45,00,000.00',
      CENTRAL_CLEARING_POOL: '₹ 2,50,00,000.00',
      VPA_INWARD_COLLECTIONS: '₹ 32,00,000.00'
    },
    parity_delta: '0.00 Δ',
    journal: []
  });

  const [inwardAmount, setInwardAmount] = useState('1000000');
  const [vpa, setVpa] = useState('buyer902@yesbank');
  const [loading, setLoading] = useState(false);

  const fetchTelemetry = async () => {
    try {
      const res = await fetch('/api/v1/telemetry');
      if (res.ok) {
        const data = await res.json();
        setTelemetry(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchTelemetry();
    const interval = setInterval(fetchTelemetry, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleReraSplit = async () => {
    setLoading(true);
    try {
      await fetch('/api/v1/rera/inward-split', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          buyer_vpa: vpa,
          amount: parseFloat(inwardAmount),
          project_id: 'PRJ-MAHARERA-091'
        })
      });
      await fetchTelemetry();
    } finally {
      setLoading(false);
    }
  };

  const handleSweep = async () => {
    setLoading(true);
    try {
      await fetch('/api/v1/liquidity/sweep', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_account: 'VPA_INWARD_COLLECTIONS',
          target_pool: 'CENTRAL_CLEARING_POOL',
          sweep_threshold: 500000
        })
      });
      await fetchTelemetry();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900 font-sans antialiased p-8">
      <header className="max-w-7xl mx-auto flex justify-between items-center pb-6 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">TBG-CORE PLATFORM</h1>
            <span className="text-[11px] font-mono font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 border border-emerald-300">
              ENGINE ACTIVE
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">Transaction Banking Clearing, Settlement & Double-Entry Ledger Rails</p>
        </div>
        <button
          onClick={fetchTelemetry}
          className="flex items-center gap-1.5 bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-xs font-medium px-3.5 py-2 rounded-lg shadow-sm transition"
        >
          <RefreshCw className="w-3.5 h-3.5 text-slate-500" /> Sync Telemetry
        </button>
      </header>

      <main className="max-w-7xl mx-auto mt-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500 flex justify-between items-center">
              <span>Total Liquid Reserve</span>
              <Database className="w-4 h-4 text-indigo-600" />
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">{telemetry.total_liquidity}</div>
            <div className="text-[11px] font-medium text-emerald-600 mt-1">● 100% Backed Reserves</div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500">RERA Escrow (70% Locked)</div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">{telemetry.balances.ESCROW_RETENTION_70}</div>
            <div className="text-[11px] text-slate-500 mt-1">Statutory Restricted Escrow</div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500">Builder Free Account (30%)</div>
            <div className="text-2xl font-bold text-slate-900 mt-2 font-mono">{telemetry.balances.BUILDER_CURRENT_30}</div>
            <div className="text-[11px] text-slate-500 mt-1">Unrestricted Operations</div>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-sm">
            <div className="text-xs font-semibold text-slate-500 flex justify-between items-center">
              <span>Double-Entry Parity</span>
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
            </div>
            <div className="text-2xl font-bold text-emerald-600 mt-2 font-mono">{telemetry.parity_delta}</div>
            <div className="text-[11px] text-emerald-700 mt-1">Σ Debits ≡ Σ Credits Guaranteed</div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Send className="w-4 h-4 text-indigo-600" />
                <h2 className="text-sm font-bold text-slate-900">Simulate Inward Collection (RERA Mandate)</h2>
              </div>
              <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                Applies the statutory split on inward clearing. 70% is routed to the escrow retention sub-account, while 30% clears to the operational current account.
              </p>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Buyer Virtual Payment Address (VPA)</label>
                  <input
                    type="text"
                    value={vpa}
                    onChange={(e) => setVpa(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
                <div>
                  <label className="block font-semibold text-slate-700 mb-1">Collection Amount (INR)</label>
                  <input
                    type="number"
                    value={inwardAmount}
                    onChange={(e) => setInwardAmount(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-xs font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
            </div>

            <button
              disabled={loading}
              onClick={handleReraSplit}
              className="mt-5 w-full bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs py-2.5 rounded-lg shadow-sm transition cursor-pointer"
            >
              Post Settlement Split (70/30)
            </button>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <SlidersHorizontal className="w-4 h-4 text-emerald-600" />
                <h2 className="text-sm font-bold text-slate-900">Automated Liquidity Sweep Rail</h2>
              </div>
              <p className="text-xs text-slate-500 mb-4 leading-relaxed">
                Sweeps surplus balances from the Inward Collections account to the Central Clearing Pool above a defined floor threshold (₹ 5,00,000).
              </p>

              <div className="p-4 bg-slate-50 border border-slate-200 rounded-lg text-xs space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-500">Source VPA Balance:</span>
                  <span className="font-mono font-semibold text-slate-800">{telemetry.balances.VPA_INWARD_COLLECTIONS}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">Floor Retention Limit:</span>
                  <span className="font-mono font-semibold text-slate-800">₹ 5,00,000.00</span>
                </div>
              </div>
            </div>

            <button
              disabled={loading}
              onClick={handleSweep}
              className="mt-5 w-full bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs py-2.5 rounded-lg shadow-sm transition cursor-pointer"
            >
              Trigger EOD Liquidity Sweep
            </button>
          </div>

          <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm flex flex-col justify-between">
            <div>
              <h2 className="text-sm font-bold text-slate-900 mb-2">How This Rail Operates</h2>
              <ul className="text-xs text-slate-600 space-y-2.5 list-disc pl-4 leading-relaxed">
                <li><strong className="text-slate-800">Idempotency & Guardrails:</strong> Every incoming packet contains a unique deterministic key preventing duplicate settlement execution.</li>
                <li><strong className="text-slate-800">Atomic Postings:</strong> State updates happen in lockstep. If a debit fails, all credit allocations are immediately rolled back.</li>
                <li><strong className="text-slate-800">Zero-Delta Parity:</strong> Every movement logs complementary Dr/Cr entries to ensure the overall balance remains neutral.</li>
              </ul>
            </div>
            <div className="text-[11px] font-mono bg-slate-100 p-2.5 rounded border border-slate-200 text-slate-600 mt-4">
              Status: Connected to local uvicorn cluster.
            </div>
          </div>
        </div>

        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-sm">
          <h2 className="text-xs font-bold text-slate-500 uppercase tracking-wider mb-4">
            Immutable Double-Entry Settlement Journal
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="text-slate-500 border-b border-slate-200 pb-2">
                <tr>
                  <th className="pb-3">Timestamp</th>
                  <th className="pb-3">Batch Ref</th>
                  <th className="pb-3">Clearing / Settlement Routing</th>
                  <th className="pb-3">Amount</th>
                  <th className="pb-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {telemetry.journal.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-slate-400">
                      No transactions posted in this session yet. Trigger a split or sweep above.
                    </td>
                  </tr>
                ) : (
                  telemetry.journal.map((tx: any) => (
                    <tr key={tx.id} className="hover:bg-slate-50 transition">
                      <td className="py-3 text-slate-500">{tx.time}</td>
                      <td className="font-semibold text-indigo-600">{tx.ref}</td>
                      <td className="text-slate-700">{tx.routing}</td>
                      <td className={tx.type === 'CREDIT' ? 'text-emerald-600 font-semibold' : 'text-slate-900 font-semibold'}>
                        {tx.amount}
                      </td>
                      <td>
                        <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {tx.type === 'CREDIT' ? <ArrowDownLeft className="w-3 h-3" /> : <ArrowUpRight className="w-3 h-3" />}
                          {tx.status}
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
