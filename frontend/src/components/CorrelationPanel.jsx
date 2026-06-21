/**
 * ==========================================================
 * MetricGuard — CorrelationPanel Component
 * ==========================================================
 * Card-based display of metric-log correlation results.
 * Clickable to open a detailed modal overlay.
 */

import { useState, useEffect } from 'react';
import { fetchCorrelations } from '../services/api';

function getScoreBreakdown(c) {
  const score = c.correlation_score ?? c.confidence / 100 ?? 0;
  const items = [];
  
  // Time Proximity Match is always true if they are correlated
  items.push({ name: 'Time Proximity Match (±60s)', weight: 30, checked: true });
  
  // Keyword Match is true if inferred cause is not Unknown
  const hasKeyword = c.inferred_cause && c.inferred_cause !== 'Unknown';
  items.push({ name: 'Keyword/Anomaly Cause Match', weight: 10, checked: hasKeyword });
  
  // Host Match
  const hasHost = !!c.host_name;
  items.push({ name: 'Host Identity Match', weight: 20, checked: hasHost });
  
  // Service Match
  const hasService = !!c.service_name;
  items.push({ name: 'Service Context Match', weight: 20, checked: hasService });
  
  // Severity Match (remaining score)
  let currentSum = 30 + (hasKeyword ? 10 : 0) + (hasHost ? 20 : 0) + (hasService ? 20 : 0);
  let severityMatched = (Math.round(score * 100) - currentSum) >= 20;
  items.push({ name: 'Severity Correlation Match', weight: 20, checked: severityMatched });
  
  return items;
}

export default function CorrelationPanel() {
  const [correlations, setCorrelations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedCorr, setSelectedCorr] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await fetchCorrelations();
        setCorrelations(data);
      } catch {
        /* empty */
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {[...Array(3)].map((_, i) => (
          <div key={i} className="skeleton h-52 rounded-2xl" />
        ))}
      </div>
    );
  }

  if (!correlations.length) {
    return (
      <div className="glass-card p-8 text-center border-slate-900">
        <p className="text-slate-500 text-xs italic">No correlation results available.</p>
      </div>
    );
  }

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {correlations.map((c, idx) => {
          const score = c.correlation_score ?? c.confidence ?? 0;
          const scoreColor = score >= 0.8 ? 'text-rose-400' : score >= 0.5 ? 'text-amber-400' : 'text-emerald-400';
          const barColor = score >= 0.8 ? '#f43f5e' : score >= 0.5 ? '#f59e0b' : '#10b981';

          return (
            <div
              key={c.id || idx}
              onClick={() => setSelectedCorr(c)}
              className="glass-card p-6 border-slate-900 flex flex-col justify-between hover:border-indigo-500/25 transition-all cursor-pointer hover:scale-[1.01]"
            >
              <div>
                {/* Score header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                      <svg className="w-4 h-4 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                      </svg>
                    </div>
                    <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                      Relation #{idx + 1}
                    </span>
                  </div>
                  <span className={`text-lg font-bold font-mono ${scoreColor}`}>
                    {(score * 100).toFixed(0)}%
                  </span>
                </div>

                {/* Score bar */}
                <div className="progress-bar mb-4">
                  <div
                    className="progress-bar-fill"
                    style={{ 
                      width: `${(score * 100).toFixed(0)}%`, 
                      background: barColor,
                      boxShadow: `0 0 8px ${barColor}40`
                    }}
                  />
                </div>

                {/* Metric anomaly */}
                <div className="mb-4">
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Metric Signal</p>
                  <p className="text-xs text-slate-200 font-semibold leading-relaxed">
                    {c.metric_anomaly_id ? `Anomaly #${c.metric_anomaly_id}` : c.root_cause || 'Unknown metric event'}
                  </p>
                </div>

                {/* Inferred Root Cause */}
                <div className="mb-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Inferred Root Cause</p>
                      <p className="text-xs text-indigo-300 font-bold leading-relaxed truncate" title={c.inferred_cause}>
                        {c.inferred_cause || 'Unknown'}
                      </p>
                    </div>
                    {c.service_name && (
                      <span className="badge badge-info shrink-0 text-[8px] uppercase tracking-wider px-2 py-0.5 mt-4">
                        {c.service_name}
                      </span>
                    )}
                  </div>
                </div>

                {/* Log anomaly */}
                <div className="mb-4">
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Correlated Log Template</p>
                  <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed font-mono bg-slate-950/40 p-2.5 rounded-lg border border-slate-900">
                    {c.log_message || c.log_anomaly_id ? (c.log_message || `Anomaly ID: ${c.log_anomaly_id}`) : 'No related log signal'}
                  </p>
                </div>
              </div>

              {/* Timestamp */}
              <div className="pt-3 border-t border-slate-900/60 mt-auto flex items-center justify-between">
                <div>
                  <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-0.5">Correlated At</p>
                  <p className="text-[10px] font-mono text-slate-500">
                    {c.created_at ? new Date(c.created_at).toLocaleString() : '—'}
                  </p>
                </div>
                <span className="text-[9px] font-bold uppercase tracking-wider text-indigo-400 flex items-center gap-1">
                  Details
                  <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Modal Details Overlay */}
      {selectedCorr && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
          <div className="glass-card w-full max-w-xl p-8 border-slate-900 shadow-2xl relative animate-scale-in max-h-[90vh] overflow-y-auto custom-scrollbar">
            {/* Close Button */}
            <button
              onClick={() => setSelectedCorr(null)}
              className="absolute top-6 right-6 text-slate-500 hover:text-slate-200 transition-colors p-1.5 rounded-lg hover:bg-slate-900/60"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>

            {/* Header */}
            <div className="mb-6">
              <div className="flex items-center gap-2.5 mb-2.5">
                <div className="w-9 h-9 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
                  </svg>
                </div>
                <h3 className="text-base font-extrabold text-slate-100">Correlation Insight #{selectedCorr.id}</h3>
              </div>
              <p className="text-xs text-slate-500">
                Detailed ML match analysis between telemetry anomaly signals and application logs.
              </p>
            </div>

            {/* Confidence Metric */}
            <div className="bg-[#090d16]/60 border border-slate-900 rounded-xl p-5 mb-6 flex items-center justify-between">
              <div>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-1">Match Confidence</p>
                <p className="text-2xl font-extrabold text-indigo-400">
                  {((selectedCorr.correlation_score ?? selectedCorr.confidence ?? 0) * 100).toFixed(0)}%
                </p>
              </div>
              <div className="w-1/2">
                <div className="progress-bar mb-1.5">
                  <div
                    className="progress-bar-fill"
                    style={{
                      width: `${((selectedCorr.correlation_score ?? selectedCorr.confidence ?? 0) * 100)}%`,
                      background: (selectedCorr.correlation_score ?? selectedCorr.confidence ?? 0) >= 0.8 ? '#10b981' : (selectedCorr.correlation_score ?? selectedCorr.confidence ?? 0) >= 0.5 ? '#f59e0b' : '#6366f1',
                    }}
                  />
                </div>
                <span className="text-[9px] text-slate-500 font-medium float-right">
                  Score Value: {(selectedCorr.correlation_score ?? selectedCorr.confidence ?? 0).toFixed(2)}
                </span>
              </div>
            </div>

            {/* Primary Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
              <div className="bg-slate-950/40 border border-slate-900/40 rounded-xl p-4">
                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1.5">Inferred Cause</p>
                <p className="text-xs text-slate-200 font-bold leading-relaxed">
                  {selectedCorr.inferred_cause || 'Unknown'}
                </p>
              </div>

              <div className="bg-slate-950/40 border border-slate-900/40 rounded-xl p-4">
                <p className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1.5">Target Service</p>
                <p className="text-xs text-indigo-400 font-bold leading-relaxed uppercase">
                  {selectedCorr.service_name || 'System-Wide'}
                </p>
              </div>
            </div>

            {/* Related Components */}
            <div className="space-y-4 mb-6">
              <div>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2">Scoring Analysis Breakdown</p>
                <div className="bg-[#090d16]/30 border border-slate-900/60 rounded-xl p-4 space-y-3 font-sans">
                  {getScoreBreakdown(selectedCorr).map((item, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2.5">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center ${
                          item.checked ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-950 text-slate-600 border border-slate-800'
                        }`}>
                          {item.checked ? (
                            <svg className="w-2.5 h-2.5" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                            </svg>
                          ) : (
                            <span className="w-1.5 h-1.5 rounded-full bg-slate-800" />
                          )}
                        </span>
                        <span className={item.checked ? 'text-slate-300' : 'text-slate-500 line-through'}>{item.name}</span>
                      </div>
                      <span className={`font-mono font-bold ${item.checked ? 'text-indigo-400' : 'text-slate-600'}`}>
                        +{item.weight}%
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2">Observed Environment</p>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-[#090d16]/20 border border-slate-900/60 rounded-xl p-3 flex flex-col justify-between">
                    <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Host Node</span>
                    <span className="font-mono text-slate-300 font-bold">{selectedCorr.host_name || '—'}</span>
                  </div>
                  <div className="bg-[#090d16]/20 border border-slate-900/60 rounded-xl p-3 flex flex-col justify-between">
                    <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Container ID</span>
                    <span className="font-mono text-slate-300 font-bold truncate" title={selectedCorr.container_id}>
                      {selectedCorr.container_id || '—'}
                    </span>
                  </div>
                </div>
              </div>

              <div>
                <p className="text-[10px] text-slate-500 font-bold uppercase tracking-wider mb-2">Mapping Reference IDs</p>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-[#090d16]/20 border border-slate-900/60 rounded-xl p-3 flex flex-col justify-between">
                    <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Metric Anomaly ID</span>
                    <span className="font-mono text-slate-300 font-bold">#{selectedCorr.metric_anomaly_id || '—'}</span>
                  </div>
                  <div className="bg-[#090d16]/20 border border-slate-900/60 rounded-xl p-3 flex flex-col justify-between">
                    <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider mb-1">Log Anomaly ID</span>
                    <span className="font-mono text-slate-300 font-bold">#{selectedCorr.log_anomaly_id || '—'}</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer / Timestamp */}
            <div className="pt-4 border-t border-slate-900/60 flex items-center justify-between text-[10px] text-slate-500">
              <span>Detected At:</span>
              <span className="font-mono">{new Date(selectedCorr.created_at).toLocaleString()}</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
