import { useState, useEffect } from 'react';
import { Activity, ShieldCheck, Database, ArrowUpRight, ArrowDownLeft, RefreshCw } from 'lucide-react';

interface Entry {
  id: string;
  time: string;
  ref: string;
  dr_cr: string;
  amount: string;
  type: 'DEBIT' | 'CREDIT';
}

export default function App() {
  const [entries, setEntries] = useState<Entry[]>([
    { id: '1', time: '17:55:01', ref: 'TXN-99021', dr_cr: 'ESCROW_CORE / VPA_POOL', amount: '₹ 4,50,000.00', type: 'CREDIT' },
    { id: '2', time: '17:52:14', ref: 'TXN-99020', dr_cr: 'SWEEP_ACCT / RESERVE_01', amount: '₹ 12,00,000.00', type: 'DEBIT' },
  ]);
  const [latency, setLatency] = useState(11);

  const triggerSweep = () => {
    const newTx: Entry = {
      id: String(Date.now()),
      time: new Date().toLocaleTimeString(),
      ref: `TXN-${Math.floor(10000 + Math.random() * 90000)}`,
      dr_cr: 'AUTO_SWEEP / POOL_L1',
      amount: '₹ 2,50,000.00',
      type: 'CREDIT'
    };
    setEntries(prev => [newTx, ...prev.slice(0, 7)]);
    setLatency(Math.floor(9 + Math.random() * 8));
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased p-8">
      {/* Top Header */}
      <header className="max-w-7xl mx-auto flex justify-between items-center pb-6 border-b border-slate-800">
        <div className="flex items-center gap-3">
          <div className="h-3 w-3 rounded-full bg-emerald-400 animate-ping" />
          <div>
            <h1 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              TBG-CORE ENGINE
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800">
                Production Cluster
              </span>
            </h1>
            <p className="text-xs text-slate-400">High-Throughput Clearing & Double-Entry Rail</p>
          </div>
        </div>
        <button 
          onClick={triggerSweep}
          className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold px-4 py-2 rounded-md transition shadow-sm"
        >
          <RefreshCw className="w-3.5 h-3.5" /> Execute Liquidity Sweep
        </button>
      </header>

      {/* Main Grid */}
      <main className="max-w-7xl mx-auto mt-8 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>Escrow Liquidity</span>
              <Database className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="text-2xl font-bold text-white mt-2 font-mono">₹ 14,85,00,000</div>
            <div className="text-[11px] text-emerald-400 mt-1">● 100% Reserve Matched</div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>Active VPAs</span>
              <Activity className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-white mt-2 font-mono">4,821</div>
            <div className="text-[11px] text-slate-400 mt-1">Double-Entry Virtual Accounts</div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>Ledger Parity</span>
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="text-2xl font-bold text-emerald-400 mt-2 font-mono">0.00 Δ</div>
            <div className="text-[11px] text-emerald-500 mt-1">Zero Out-of-Balance Events</div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-lg p-5">
            <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
              <span>Gateway Latency</span>
              <Activity className="w-4 h-4 text-cyan-400" />
            </div>
            <div className="text-2xl font-bold text-cyan-400 mt-2 font-mono">{latency} ms</div>
            <div className="text-[11px] text-slate-400 mt-1">Loopback Telemetry</div>
          </div>
        </div>

        {/* Ledger Event Table */}
        <div className="bg-slate-900 border border-slate-800 rounded-lg p-6">
          <h2 className="text-xs uppercase font-semibold text-slate-400 tracking-wider mb-4">
            Real-Time Settlement Journal
          </h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="text-slate-400 border-b border-slate-800 pb-2">
                <tr>
                  <th className="pb-3">Timestamp</th>
                  <th className="pb-3">Batch Ref</th>
                  <th className="pb-3">Routing Nodes</th>
                  <th className="pb-3">Amount</th>
                  <th className="pb-3">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {entries.map(tx => (
                  <tr key={tx.id} className="hover:bg-slate-800/30 transition">
                    <td className="py-3 text-slate-400">{tx.time}</td>
                    <td className="text-indigo-400 font-semibold">{tx.ref}</td>
                    <td className="text-slate-300">{tx.dr_cr}</td>
                    <td className={tx.type === 'CREDIT' ? 'text-emerald-400 font-semibold' : 'text-slate-200'}>
                      {tx.amount}
                    </td>
                    <td>
                      <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800">
                        {tx.type === 'CREDIT' ? <ArrowDownLeft className="w-3 h-3" /> : <ArrowUpRight className="w-3 h-3" />}
                        POSTED
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}