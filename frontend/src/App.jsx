import { useState, useEffect } from 'react';
import MetricCards from './components/MetricCards';
import MetricsChart from './components/MetricsChart';
import MetricAnomalies from './components/MetricAnomalies';
import LogAnomalies from './components/LogAnomalies';
import CorrelationPanel from './components/CorrelationPanel';
import RCAView from './components/RCAView';
import DependencyGraph from './components/DependencyGraph';
import ServiceImpactView from './components/ServiceImpactView';
import IncidentTable from './components/IncidentTable';
import RecommendationPanel from './components/RecommendationPanel';
import LiveAlerts from './components/LiveAlerts';
import ReportsPanel from './components/ReportsPanel';
import api from './services/api';

function App() {
  const [activeTab, setActiveTab] = useState('overview');
  const [time, setTime] = useState(new Date());
  const [health, setHealth] = useState({ status: 'unknown', db: 'unknown' });

  // Update clock every second
  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  // Fetch system health every 15 seconds
  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const res = await api.get('/health');
        setHealth({ status: res.data.status, db: res.data.database });
      } catch {
        setHealth({ status: 'error', db: 'disconnected' });
      }
    };
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const healthBadge = () => {
    const s = health.status.toLowerCase();
    if (s === 'healthy') return 'badge-resolved';
    if (s === 'degraded') return 'badge-warning';
    return 'badge-critical';
  };

  return (
    <div className="flex min-h-screen bg-[#030712] text-slate-100 antialiased selection:bg-indigo-500/30 selection:text-white">
      {/* ─── SIDEBAR ────────────────────────────────────────── */}
      <aside className="w-64 border-r border-slate-900 bg-[#090d16]/80 backdrop-blur-xl flex flex-col shrink-0">
        {/* Title / Brand Header */}
        <div className="h-16 flex items-center px-6 border-b border-slate-900 gap-3">
          <svg className="w-6 h-6 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
          <span className="font-extrabold text-lg tracking-tight bg-gradient-to-r from-indigo-300 via-indigo-400 to-violet-400 bg-clip-text text-transparent">
            MetricGuard
          </span>
          <span className="flex h-2 w-2 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
        </div>

        {/* Navigation Tabs */}
        <nav className="flex-1 px-4 py-6 space-y-1">
          <button
            onClick={() => setActiveTab('overview')}
            className={`sidebar-link w-full text-left flex items-center gap-3 ${
              activeTab === 'overview' ? 'active' : ''
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <rect x="3" y="3" width="7" height="9" rx="1" />
              <rect x="14" y="3" width="7" height="5" rx="1" />
              <rect x="14" y="12" width="7" height="9" rx="1" />
              <rect x="3" y="16" width="7" height="5" rx="1" />
            </svg>
            System Overview
          </button>
          
          <button
            onClick={() => setActiveTab('anomalies')}
            className={`sidebar-link w-full text-left flex items-center gap-3 ${
              activeTab === 'anomalies' ? 'active' : ''
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            Anomalies Feed
          </button>

          <button
            onClick={() => setActiveTab('topology')}
            className={`sidebar-link w-full text-left flex items-center gap-3 ${
              activeTab === 'topology' ? 'active' : ''
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <circle cx="12" cy="5" r="3" />
              <circle cx="5" cy="18" r="3" />
              <circle cx="19" cy="18" r="3" />
              <path d="M12 8v4M5 15l5-3M19 15l-5-3" />
            </svg>
            Service Topology
          </button>

          <button
            onClick={() => setActiveTab('incidents')}
            className={`sidebar-link w-full text-left flex items-center gap-3 ${
              activeTab === 'incidents' ? 'active' : ''
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
            </svg>
            Incident Room
          </button>

          <button
            onClick={() => setActiveTab('reports')}
            className={`sidebar-link w-full text-left flex items-center gap-3 ${
              activeTab === 'reports' ? 'active' : ''
            }`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            Automated Reports
          </button>
        </nav>

        {/* Footer info */}
        <div className="p-4 border-t border-slate-900 bg-slate-950/20 text-[10px] text-slate-500 space-y-1">
          <p className="font-mono text-slate-600">Models: IsolationForest v1.0</p>
          <p className="font-mono text-slate-600">Models: LSTM Autoencoder v1.2</p>
          <p className="text-slate-600">© 2026 MetricGuard AIOps</p>
        </div>
      </aside>

      {/* ─── MAIN CONTENT AREA ──────────────────────────────── */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Workspace Header */}
        <header className="h-16 border-b border-slate-900 bg-[#090d16]/80 backdrop-blur-xl flex items-center justify-between px-6 md:px-12 lg:px-20 workspace-header z-10 shrink-0">
          <div className="flex items-center gap-4">
            <h2 className="text-sm font-bold tracking-tight text-slate-200 uppercase">
              {activeTab === 'overview' ? 'Telemetry & System Health' : `${activeTab} Management`}
            </h2>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-600 font-medium">Status:</span>
              <span className={`badge ${healthBadge()}`}>{health.status}</span>
            </div>
          </div>

          <div className="flex items-center gap-6">
            <div className="text-right">
              <p className="text-xs text-slate-500 font-semibold uppercase tracking-wider">Database (TiDB)</p>
              <p className="text-[10px] text-indigo-400/80 font-mono font-bold uppercase">{health.db}</p>
            </div>
            <div className="h-8 w-[1px] bg-slate-900" />
            <div className="text-slate-400 font-mono text-xs font-semibold bg-slate-950/40 px-3 py-1.5 rounded-lg border border-slate-900">
              {time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true })}
            </div>
          </div>
        </header>

        {/* Workspace Scroll Panel */}
        <div className="flex-1 overflow-y-auto p-6 md:p-12 lg:p-20 workspace-panel space-y-8 animate-slide-up">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <>
              {/* Metric Overview Cards */}
              <div className="space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
                  </svg>
                  System Resource Status
                </h3>
                <MetricCards />
              </div>

              {/* Resource Trend Charts */}
              <div className="space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M7 12l3-3 3 3 4-4M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                  Resource Trend Analysis
                </h3>
                <MetricsChart />
              </div>

              {/* RCA Summary Grid & Live Alert Tracker */}
              <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
                <div className="xl:col-span-2 space-y-4">
                  <h3 className="section-title">
                    <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    ML Root Cause Breakdown
                  </h3>
                  <RCAView />
                </div>
                <div className="space-y-4">
                  <h3 className="section-title">
                    <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                    </svg>
                    Live Alert Stream
                  </h3>
                  <LiveAlerts />
                </div>
              </div>
            </>
          )}

          {/* TAB 2: ANOMALIES FEED */}
          {activeTab === 'anomalies' && (
            <>
              {/* Metric & Log Anomalies Side-by-Side */}
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                <div className="space-y-4">
                  <h3 className="section-title">
                    <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
                    </svg>
                    Metric Anomalies Log
                  </h3>
                  <MetricAnomalies />
                </div>
                <div className="space-y-4">
                  <h3 className="section-title">
                    <svg className="w-5 h-5 text-violet-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                    Log Anomalies Log
                  </h3>
                  <LogAnomalies />
                </div>
              </div>

              {/* Metric-Log Correlation Engine Panel */}
              <div className="space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                  Metric-Log Correlation Insights
                </h3>
                <CorrelationPanel />
              </div>
            </>
          )}

          {/* TAB 3: TOPOLOGY & SERVICE DEPENDENCY */}
          {activeTab === 'topology' && (
            <>
              {/* Service Impact Dashboard */}
              <div className="space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-rose-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  Service Impact Analysis
                </h3>
                <ServiceImpactView />
              </div>

              {/* Interactive Dependency Graph */}
              <div className="space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <circle cx="12" cy="5" r="3" />
                    <circle cx="5" cy="18" r="3" />
                    <circle cx="19" cy="18" r="3" />
                    <path d="M12 8v4M5 15l5-3M19 15l-5-3" />
                  </svg>
                  Interactive Topology Map
                </h3>
                <DependencyGraph />
              </div>
            </>
          )}

          {/* TAB 4: INCIDENTS & ACTIONS */}
          {activeTab === 'incidents' && (
            <div className="grid grid-cols-1 xl:grid-cols-5 gap-6">
              {/* Incident Table */}
              <div className="xl:col-span-3 space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-amber-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  Active Incidents
                </h3>
                <IncidentTable />
              </div>

              {/* Recommendation Panel */}
              <div className="xl:col-span-2 space-y-4">
                <h3 className="section-title">
                  <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                  </svg>
                  Smart Remediation Suggestions
                </h3>
                <RecommendationPanel />
              </div>
            </div>
          )}

          {/* TAB 5: AUTOMATED REPORTS */}
          {activeTab === 'reports' && (
            <div className="space-y-4">
              <h3 className="section-title">
                <svg className="w-5 h-5 text-indigo-400" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
                System Incident Reporting
              </h3>
              <ReportsPanel />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

export default App;
