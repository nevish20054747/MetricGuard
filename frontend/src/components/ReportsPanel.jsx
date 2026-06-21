/**
 * ==========================================================
 * MetricGuard — ReportsPanel Component
 * ==========================================================
 * Allows operators to select active incidents, choose PDF or CSV export
 * formats, trigger the report generation service, and download reports.
 */

import { useState, useEffect, useCallback } from 'react';
import { fetchIncidents, fetchReports, generateReport, getReportDownloadUrl } from '../services/api';

export default function ReportsPanel() {
  const [incidents, setIncidents] = useState([]);
  const [reports, setReports] = useState([]);
  
  const [selectedIncident, setSelectedIncident] = useState('');
  const [pdfSelected, setPdfSelected] = useState(true);
  const [csvSelected, setCsvSelected] = useState(true);
  
  const [loadingIncidents, setLoadingIncidents] = useState(true);
  const [loadingReports, setLoadingReports] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  // Fetch incidents list
  useEffect(() => {
    (async () => {
      try {
        const res = await fetchIncidents({ limit: 100 });
        const incs = res.incidents || [];
        setIncidents(incs);
        if (incs.length > 0) {
          setSelectedIncident(incs[0].incident_id);
        }
      } catch (err) {
        console.error('Failed to fetch incidents', err);
      } finally {
        setLoadingIncidents(false);
      }
    })();
  }, []);

  // Fetch historical reports list
  const loadReports = useCallback(async () => {
    setLoadingReports(true);
    try {
      const data = await fetchReports();
      setReports(data || []);
    } catch (err) {
      console.error('Failed to load reports', err);
    } finally {
      setLoadingReports(false);
    }
  }, []);

  useEffect(() => {
    loadReports();
  }, [loadReports]);

  // Handle generation action
  const handleGenerate = async (e) => {
    e.preventDefault();
    if (!selectedIncident) {
      setErrorMsg('Please select a valid incident first.');
      return;
    }
    const selectedFormats = [];
    if (pdfSelected) selectedFormats.push('pdf');
    if (csvSelected) selectedFormats.push('csv');

    if (selectedFormats.length === 0) {
      setErrorMsg('Please select at least one file format (PDF or CSV).');
      return;
    }

    setGenerating(true);
    setErrorMsg('');
    setSuccessMsg('');

    try {
      const response = await generateReport(selectedIncident, selectedFormats);
      if (response.status === 'success') {
        setSuccessMsg(`Successfully generated report ${response.report_id}!`);
        await loadReports();
      } else {
        setErrorMsg('Report generation failed. Please try again.');
      }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Report generation failed.';
      setErrorMsg(msg);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-5 gap-8">
      {/* ─── GENERATION CONFIGURATION (LEFT COLUMN) ──────────── */}
      <div className="lg:col-span-2 space-y-6">
        <div className="glass-card border-slate-900 shadow-2xl flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <h4 className="text-sm font-bold text-slate-200 uppercase tracking-wide">Generate Incident Report</h4>
                <p className="text-[10px] text-slate-500 font-bold uppercase mt-0.5">Automated Report Generation Service</p>
              </div>
            </div>

            {loadingIncidents ? (
              <div className="space-y-4">
                <div className="skeleton h-10 rounded-xl" />
                <div className="skeleton h-20 rounded-xl" />
              </div>
            ) : incidents.length === 0 ? (
              <div className="p-6 text-center bg-slate-950/20 rounded-xl border border-slate-900/60">
                <p className="text-slate-500 text-xs italic">No incidents available to report on.</p>
              </div>
            ) : (
              <form onSubmit={handleGenerate} className="space-y-6">
                {/* Incident Dropdown */}
                <div className="space-y-2">
                  <label htmlFor="incidentSelect" className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                    Select Source Incident
                  </label>
                  <select
                    id="incidentSelect"
                    value={selectedIncident}
                    onChange={(e) => setSelectedIncident(e.target.value)}
                    className="w-full bg-[#090d16] text-slate-200 text-xs font-semibold px-4 py-3 rounded-xl border border-slate-800 focus:outline-none focus:border-indigo-500 transition-colors"
                  >
                    {incidents.map((inc) => (
                      <option key={inc.incident_id} value={inc.incident_id}>
                        {inc.incident_id} — {inc.root_cause.length > 30 ? `${inc.root_cause.substring(0, 30)}...` : inc.root_cause} ({inc.severity})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Formats Checklist */}
                <div className="space-y-3">
                  <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider block">
                    Export Formats
                  </span>
                  
                  <div className="grid grid-cols-2 gap-4">
                    {/* PDF Format Selection */}
                    <label 
                      onClick={() => setPdfSelected(!pdfSelected)}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200 cursor-pointer select-none ${
                        pdfSelected 
                          ? 'bg-indigo-500/10 border-indigo-500/30 text-slate-200' 
                          : 'bg-[#090d16]/30 border-slate-800/80 text-slate-500 hover:text-slate-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={pdfSelected}
                        onChange={() => {}} // handled by click on label
                        className="hidden"
                      />
                      <div className={`w-4 h-4 rounded-md border flex items-center justify-center transition-all ${
                        pdfSelected ? 'bg-indigo-600 border-indigo-500' : 'border-slate-700'
                      }`}>
                        {pdfSelected && (
                          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                      <div className="flex flex-col text-left">
                        <span className="text-xs font-bold font-mono">PDF Format</span>
                        <span className="text-[9px] text-slate-500 font-medium">Standard formatted report</span>
                      </div>
                    </label>

                    {/* CSV Format Selection */}
                    <label 
                      onClick={() => setCsvSelected(!csvSelected)}
                      className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-all duration-200 cursor-pointer select-none ${
                        csvSelected 
                          ? 'bg-emerald-500/10 border-emerald-500/30 text-slate-200' 
                          : 'bg-[#090d16]/30 border-slate-800/80 text-slate-500 hover:text-slate-400'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={csvSelected}
                        onChange={() => {}} // handled by click on label
                        className="hidden"
                      />
                      <div className={`w-4 h-4 rounded-md border flex items-center justify-center transition-all ${
                        csvSelected ? 'bg-emerald-600 border-emerald-500' : 'border-slate-700'
                      }`}>
                        {csvSelected && (
                          <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" strokeWidth="3" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                          </svg>
                        )}
                      </div>
                      <div className="flex flex-col text-left">
                        <span className="text-xs font-bold font-mono">CSV Format</span>
                        <span className="text-[9px] text-slate-500 font-medium">Raw metrics summary</span>
                      </div>
                    </label>
                  </div>
                </div>

                {/* Feedback Alerts */}
                {errorMsg && (
                  <div className="p-3 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded-xl text-xs font-semibold leading-relaxed animate-pulse">
                    ⚠️ {errorMsg}
                  </div>
                )}

                {successMsg && (
                  <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-semibold leading-relaxed">
                    ✨ {successMsg}
                  </div>
                )}

                {/* Submit button */}
                <button
                  type="submit"
                  disabled={generating}
                  className={`w-full py-3.5 rounded-xl font-bold text-xs uppercase tracking-wider transition-all duration-200 cursor-pointer flex items-center justify-center gap-2 ${
                    generating
                      ? 'bg-slate-800 text-slate-500 border border-slate-700/50 cursor-not-allowed'
                      : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-600/20 active:scale-98'
                  }`}
                >
                  {generating ? (
                    <>
                      <svg className="animate-spin h-4 w-4 text-slate-500" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Assembling Report Data...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                      </svg>
                      Compile and Export
                    </>
                  )}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>

      {/* ─── HISTORICAL REPORT LOGS (RIGHT COLUMN) ────────────── */}
      <div className="lg:col-span-3 space-y-4">
        <div className="glass-card p-0 overflow-hidden border-slate-900 shadow-2xl">
          <div className="flex items-center justify-between p-5 border-b border-slate-900/60 bg-slate-950/20">
            <div className="flex items-center gap-2.5">
              <svg className="w-4 h-4 text-slate-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
              </svg>
              <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">Reports Log History</span>
            </div>
            <button 
              onClick={loadReports}
              disabled={loadingReports}
              className="text-slate-500 hover:text-indigo-400 transition-colors p-1.5 rounded-lg hover:bg-slate-900/30 cursor-pointer disabled:opacity-50"
              title="Refresh logs list"
            >
              <svg className={`w-3.5 h-3.5 ${loadingReports ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182m0-4.991v4.99" />
              </svg>
            </button>
          </div>

          {loadingReports ? (
            <div className="p-6"><div className="skeleton h-56 rounded-xl" /></div>
          ) : reports.length === 0 ? (
            <div className="p-16 text-center">
              <svg className="w-8 h-8 text-slate-700 mx-auto mb-3" fill="none" stroke="currentColor" strokeWidth="1.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
              </svg>
              <p className="text-slate-500 text-xs italic">No reports generated yet. Configure and compile one on the left.</p>
            </div>
          ) : (
            <div className="overflow-x-auto max-h-[500px] overflow-y-auto custom-scrollbar">
              <table className="w-full border-collapse text-left text-xs">
                <thead>
                  <tr className="bg-slate-950/40 border-b border-slate-900/60 sticky top-0 z-10">
                    <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Report ID</th>
                    <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Incident ID</th>
                    <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Created At</th>
                    <th className="px-6 py-4 font-bold text-slate-400 uppercase tracking-wider text-[10px]">Downloads</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-900/30">
                  {reports.map((rep) => {
                    const formats = rep.available_formats || [];
                    const hasPdf = formats.includes('pdf');
                    const hasCsv = formats.includes('csv');

                    return (
                      <tr key={rep.report_id} className="hover:bg-indigo-500/[0.01] transition-colors duration-150">
                        <td className="px-6 py-4 font-mono font-bold text-indigo-400">
                          {rep.report_id}
                        </td>
                        <td className="px-6 py-4 font-mono text-slate-300 font-semibold">
                          {rep.incident_id}
                        </td>
                        <td className="px-6 py-4 text-slate-500 font-mono text-[10px] whitespace-nowrap">
                          {rep.created_at ? new Date(rep.created_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2.5">
                            {/* PDF Download Link */}
                            {hasPdf ? (
                              <a
                                href={getReportDownloadUrl(rep.report_id, 'pdf')}
                                className="px-2.5 py-1 rounded bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 hover:text-indigo-300 border border-indigo-500/20 hover:border-indigo-500/30 text-[10px] font-bold font-mono transition-all decoration-none flex items-center gap-1 cursor-pointer"
                                title="Download PDF Report"
                              >
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                                </svg>
                                PDF
                              </a>
                            ) : (
                              <span className="px-2.5 py-1 rounded bg-slate-900/40 text-slate-600 border border-transparent text-[10px] font-bold font-mono select-none">
                                PDF N/A
                              </span>
                            )}

                            {/* CSV Download Link */}
                            {hasCsv ? (
                              <a
                                href={getReportDownloadUrl(rep.report_id, 'csv')}
                                className="px-2.5 py-1 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 hover:text-emerald-300 border border-emerald-500/20 hover:border-emerald-500/30 text-[10px] font-bold font-mono transition-all decoration-none flex items-center gap-1 cursor-pointer"
                                title="Download CSV Data"
                              >
                                <svg className="w-3 h-3" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
                                </svg>
                                CSV
                              </a>
                            ) : (
                              <span className="px-2.5 py-1 rounded bg-slate-900/40 text-slate-600 border border-transparent text-[10px] font-bold font-mono select-none">
                                CSV N/A
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
