/**
 * ==========================================================
 * MetricGuard — KnowledgeBasePanel Component
 * ==========================================================
 * Integrates the Historical Incident Analytics and the Similar
 * Incidents search/remediation suggestion panels.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchIncidents, fetchReports } from '../services/api';
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function KnowledgeBasePanel() {
  const [activeIncidents, setActiveIncidents] = useState([]);
  const [archivedIncidents, setArchivedIncidents] = useState([]);
  const [rcaHistory, setRcaHistory] = useState([]);
  const [resolutionsHistory, setResolutionsHistory] = useState([]);
  
  // Similar search states
  const [selectedIncidentId, setSelectedIncidentId] = useState('');
  const [searchTitle, setSearchTitle] = useState('');
  const [searchDesc, setSearchDesc] = useState('');
  const [similarMatches, setSimilarMatches] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  
  // Loading states
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingActive, setLoadingActive] = useState(true);

  // Load archived history
  const loadHistory = useCallback(async () => {
    setLoadingHistory(true);
    try {
      const incsRes = await axios.get(`${API_BASE}/knowledge/incidents`);
      const rcasRes = await axios.get(`${API_BASE}/knowledge/rca`);
      const resesRes = await axios.get(`${API_BASE}/knowledge/resolutions`);
      
      setArchivedIncidents(incsRes.data || []);
      setRcaHistory(rcasRes.data || []);
      setResolutionsHistory(resesRes.data || []);
    } catch (err) {
      console.error('Failed to load knowledge base history', err);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // Load active incidents for dropdown selector
  useEffect(() => {
    (async () => {
      try {
        const res = await fetchIncidents({ limit: 50 });
        const incs = res.incidents || [];
        setActiveIncidents(incs);
        if (incs.length > 0) {
          setSelectedIncidentId(incs[0].incident_id);
          // Auto-trigger search for the first active incident
          handleSearchForIncident(incs[0]);
        }
      } catch (err) {
        console.error('Failed to load active incidents', err);
      } finally {
        setLoadingActive(false);
      }
    })();
    loadHistory();
  }, [loadHistory]);

  // Handle similarity search for a specific active incident
  const handleSearchForIncident = async (inc) => {
    setSearching(true);
    setSearchError('');
    setSimilarMatches([]);
    
    // Autofill text search fields
    setSearchTitle(inc.root_cause);
    setSearchDesc(`Incident affecting ${inc.impacted_services} with severity ${inc.severity}.`);

    try {
      const res = await axios.post(`${API_BASE}/knowledge/similar`, {
        title: inc.root_cause,
        description: `Incident affecting ${inc.impacted_services} with severity ${inc.severity}.`
      });
      setSimilarMatches(res.data.matches || []);
    } catch (err) {
      setSearchError('Failed to search similar incidents.');
    } finally {
      setSearching(false);
    }
  };

  // Trigger search when active incident dropdown changes
  const handleSelectActiveIncident = (e) => {
    const incId = e.target.value;
    setSelectedIncidentId(incId);
    const inc = activeIncidents.find(x => x.incident_id === incId);
    if (inc) {
      handleSearchForIncident(inc);
    }
  };

  // Handle custom title/desc search
  const handleCustomSearch = async (e) => {
    e.preventDefault();
    if (!searchTitle.trim()) {
      setSearchError('Search title cannot be empty.');
      return;
    }
    
    setSearching(true);
    setSearchError('');
    setSimilarMatches([]);
    setSelectedIncidentId(''); // Clear dropdown select since we are running custom

    try {
      const res = await axios.post(`${API_BASE}/knowledge/similar`, {
        title: searchTitle,
        description: searchDesc
      });
      setSimilarMatches(res.data.matches || []);
    } catch (err) {
      setSearchError('Failed to search similar incidents.');
    } finally {
      setSearching(false);
    }
  };

  // ─── Metrics Computations ───────────────────────────────
  const totalArchived = archivedIncidents.length;
  
  // Calculate most common RCA
  const getMostCommonRca = () => {
    if (archivedIncidents.length === 0) return 'None';
    const counts = {};
    archivedIncidents.forEach(inc => {
      if (inc.root_cause) {
        counts[inc.root_cause] = (counts[inc.root_cause] || 0) + 1;
      }
    });
    return Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b, 'None');
  };

  // Calculate most common Resolution
  const getMostCommonResolution = () => {
    if (archivedIncidents.length === 0) return 'None';
    const counts = {};
    archivedIncidents.forEach(inc => {
      if (inc.resolution) {
        counts[inc.resolution] = (counts[inc.resolution] || 0) + 1;
      }
    });
    return Object.keys(counts).reduce((a, b) => counts[a] > counts[b] ? a : b, 'None');
  };

  return (
    <div className="space-y-8 animate-slide-up">
      {/* ─── HISTORICAL INCIDENT PANEL (OVERALL ANALYTICS) ──── */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Total Archived Card */}
        <div className="glass-card border-slate-900 shadow-xl flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
            </svg>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Archived Incidents</span>
            <span className="text-2xl font-extrabold text-slate-100 font-mono mt-0.5">{totalArchived}</span>
          </div>
        </div>

        {/* Most Common RCA */}
        <div className="glass-card border-slate-900 shadow-xl flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-amber-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Top Root Cause</span>
            <span className="text-sm font-bold text-slate-200 mt-0.5 block truncate max-w-[240px]" title={getMostCommonRca()}>
              {getMostCommonRca()}
            </span>
          </div>
        </div>

        {/* Most Common Resolution */}
        <div className="glass-card border-slate-900 shadow-xl flex items-center gap-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
            <svg className="w-6 h-6 text-emerald-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <div>
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider block">Common Resolution</span>
            <span className="text-sm font-bold text-slate-200 mt-0.5 block truncate max-w-[240px]" title={getMostCommonResolution()}>
              {getMostCommonResolution()}
            </span>
          </div>
        </div>
      </div>

      {/* ─── SIMILAR INCIDENTS COMPARISON SEARCH & SUGGESTION TOOL ─── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
        {/* Search Input Box */}
        <div className="lg:col-span-2 space-y-6">
          <div className="glass-card border-slate-900 shadow-2xl">
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-200 uppercase tracking-wide">Similar Incident Search</h4>
                <p className="text-[10px] text-slate-500 font-bold uppercase mt-0.5">Automated Resolution Advisor</p>
              </div>
            </div>

            {/* Active Incident Dropdown Lookup */}
            {!loadingActive && activeIncidents.length > 0 && (
              <div className="space-y-2 mb-6">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                  Link Active Incident
                </label>
                <select
                  value={selectedIncidentId}
                  onChange={handleSelectActiveIncident}
                  className="w-full bg-[#090d16] text-slate-200 text-xs font-semibold px-4 py-3 rounded-xl border border-slate-800 focus:outline-none focus:border-indigo-500 transition-colors"
                >
                  <option value="">-- Custom Custom Search --</option>
                  {activeIncidents.map((inc) => (
                    <option key={inc.incident_id} value={inc.incident_id}>
                      {inc.incident_id} — {inc.root_cause}
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Custom Search Form */}
            <form onSubmit={handleCustomSearch} className="space-y-4">
              <div className="space-y-2">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                  Incident Title / Cause
                </label>
                <input
                  type="text"
                  value={searchTitle}
                  onChange={(e) => setSearchTitle(e.target.value)}
                  placeholder="e.g. disk failure"
                  className="w-full bg-[#090d16] text-slate-200 text-xs px-4 py-3 rounded-xl border border-slate-800 focus:outline-none focus:border-indigo-500 transition-colors"
                />
              </div>

              <div className="space-y-2">
                <label className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                  Incident Description
                </label>
                <textarea
                  value={searchDesc}
                  onChange={(e) => setSearchDesc(e.target.value)}
                  placeholder="e.g. Storage node namenode is unavailable"
                  rows="3"
                  className="w-full bg-[#090d16] text-slate-200 text-xs px-4 py-3 rounded-xl border border-slate-800 focus:outline-none focus:border-indigo-500 transition-colors resize-none"
                />
              </div>

              {searchError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs font-semibold">
                  ⚠️ {searchError}
                </div>
              )}

              <button
                type="submit"
                disabled={searching}
                className="w-full py-3.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs uppercase tracking-wider transition-all shadow-lg shadow-indigo-600/20 active:scale-98 cursor-pointer flex items-center justify-center gap-2"
              >
                {searching ? (
                  <>
                    <svg className="animate-spin h-4 w-4 text-slate-400" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                    Matching vector vectors...
                  </>
                ) : (
                  <>Search Past Resolutions</>
                )}
              </button>
            </form>
          </div>
        </div>

        {/* Similar Incidents Matches Output */}
        <div className="lg:col-span-3 space-y-4">
          <div className="glass-card border-slate-900 shadow-2xl h-full flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                </div>
                <div>
                  <h4 className="text-sm font-bold text-slate-200 uppercase tracking-wide">Historical Resolutions Found</h4>
                  <p className="text-[10px] text-slate-500 font-bold uppercase mt-0.5">Recommendations from Similar Incidents</p>
                </div>
              </div>

              {searching ? (
                <div className="space-y-4">
                  <div className="skeleton h-24 rounded-xl" />
                  <div className="skeleton h-24 rounded-xl" />
                </div>
              ) : similarMatches.length === 0 ? (
                <div className="p-12 text-center bg-slate-950/20 rounded-2xl border border-slate-900/60">
                  <svg className="w-8 h-8 text-slate-700 mx-auto mb-3" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M15.182 15.182a4.5 4.5 0 01-6.364 0M21 12a9 9 0 11-18 0 9 9 0 0118 0zM9.75 9.75c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
                  </svg>
                  <p className="text-slate-500 text-xs italic">No matching historical incidents with similarity score &ge; 70% found.</p>
                </div>
              ) : (
                <div className="space-y-4 overflow-y-auto max-h-[360px] pr-2 custom-scrollbar">
                  {similarMatches.map((match) => {
                    const scorePct = (match.similarity_score * 100).toFixed(0);
                    const color = match.similarity_score >= 0.9 ? '#10b981' : '#f59e0b';
                    
                    return (
                      <div key={match.incident_id} className="p-5 bg-slate-950/45 rounded-2xl border border-slate-900 hover:border-indigo-500/20 transition-all flex flex-col gap-3">
                        <div className="flex items-center justify-between">
                          <span className="font-mono text-indigo-400 font-bold text-xs">
                            {match.incident_id}
                          </span>
                          <span className="text-xs font-bold font-mono" style={{ color }}>
                            {scorePct}% Match
                          </span>
                        </div>

                        <div>
                          <span className="text-[9px] text-slate-500 font-bold uppercase tracking-wider block mb-1">
                            Diagnosed Cause
                          </span>
                          <p className="text-xs text-slate-300 font-sans">{match.root_cause}</p>
                        </div>

                        <div className="p-3 bg-indigo-500/[0.03] border border-indigo-500/10 rounded-xl">
                          <span className="text-[9px] text-indigo-400 font-bold uppercase tracking-wider block mb-1">
                            Suggested Resolution
                          </span>
                          <p className="text-xs text-slate-200 font-semibold leading-relaxed font-sans">{match.resolution}</p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ─── HISTORICAL INCIDENTS HISTORY LOG TABLE ─────────── */}
      <div className="glass-card p-0 overflow-hidden border-slate-900 shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-slate-900/60 bg-slate-950/20">
          <div className="flex items-center gap-2.5">
            <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Knowledge Base Archived Logs</span>
          </div>
          <button
            onClick={loadHistory}
            disabled={loadingHistory}
            className="text-slate-500 hover:text-indigo-400 transition-colors p-1.5 rounded-lg hover:bg-slate-900/30 cursor-pointer disabled:opacity-50"
            title="Refresh history"
          >
            <svg className={`w-3.5 h-3.5 ${loadingHistory ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
            </svg>
          </button>
        </div>

        {loadingHistory ? (
          <div className="p-6"><div className="skeleton h-56 rounded-xl" /></div>
        ) : archivedIncidents.length === 0 ? (
          <div className="p-16 text-center">
            <p className="text-slate-500 text-xs italic">No resolved incidents archived in the Knowledge Base yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[500px] overflow-y-auto custom-scrollbar">
            <table className="w-full border-collapse text-left text-xs">
              <thead>
                <tr className="bg-slate-950/40 border-b border-slate-900/60 sticky top-0 z-10">
                  <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Incident ID</th>
                  <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Service</th>
                  <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Severity</th>
                  <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Root Cause</th>
                  <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Resolution Action Taken</th>
                  <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Resolved At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-900/30">
                {archivedIncidents.map((inc) => (
                  <tr key={inc.incident_id} className="hover:bg-indigo-500/[0.01] transition-colors duration-150">
                    <td className="px-6 py-4 font-mono font-bold text-indigo-400">
                      {inc.incident_id}
                    </td>
                    <td className="px-6 py-4 text-slate-300 font-semibold font-mono">
                      {inc.service_name?.toUpperCase() || '—'}
                    </td>
                    <td className="px-6 py-4">
                      <span className={`badge ${
                        (inc.severity || '').toLowerCase() === 'critical' ? 'badge-critical' :
                        (inc.severity || '').toLowerCase() === 'high' ? 'badge-warning' : 'badge-low'
                      }`}>
                        {inc.severity}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-300 font-medium">
                      {inc.root_cause}
                    </td>
                    <td className="px-6 py-4 text-slate-400 leading-relaxed font-sans max-w-xs truncate" title={inc.resolution}>
                      {inc.resolution}
                    </td>
                    <td className="px-6 py-4 text-slate-500 font-mono text-[10px] whitespace-nowrap">
                      {inc.resolved_at ? new Date(inc.resolved_at).toLocaleString() : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
