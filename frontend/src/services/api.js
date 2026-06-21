/**
 * ==========================================================
 * MetricGuard — Centralized API Service  (api.js)
 * ==========================================================
 *
 * Phase 15: Unified AIOps Dashboard
 *
 * Axios-based API client for all backend endpoints.
 * Base URL defaults to http://localhost:8000.
 */

import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
});

// ─── Metrics ─────────────────────────────────────────────
export const fetchMetrics = (limit = 50) =>
  api.get('/metrics/', { params: { limit } }).then(r => r.data);

// ─── Metric Anomalies ────────────────────────────────────
export const fetchMetricAnomalies = (limit = 50) =>
  api.get('/anomalies/', { params: { limit, sort_by: 'timestamp', sort_order: 'desc' } }).then(r => r.data);

// ─── Log Anomalies ───────────────────────────────────────
export const fetchLogAnomalies = (minutes = 60, limit = 50) =>
  api.get('/log-anomalies', { params: { minutes, limit } }).then(r => r.data);

// ─── Correlations ────────────────────────────────────────
export const fetchCorrelations = () =>
  api.get('/correlations/latest').then(r => r.data);

// ─── RCA Stats ───────────────────────────────────────────
export const fetchRCAStats = () =>
  api.get('/ml/rca/stats').then(r => r.data);

// ─── Service Dependency Graph ────────────────────────────
export const fetchServiceGraph = () =>
  api.get('/services/graph').then(r => r.data);

// ─── Service Impact Dashboard ────────────────────────────
export const fetchServiceDashboard = () =>
  api.get('/services/dashboard').then(r => r.data);

// ─── Incidents ───────────────────────────────────────────
export const fetchIncidents = (params = {}) =>
  api.get('/incidents/', { params: { page: 1, limit: 20, ...params } }).then(r => r.data);

// ─── Incident Recommendations ────────────────────────────
export const fetchIncidentRecommendations = (incidentId) =>
  api.get(`/incidents/${incidentId}/recommendations`).then(r => r.data);

// ─── Alerts ──────────────────────────────────────────────
export const fetchAlerts = () =>
  api.get('/alerts').then(r => r.data);

// ─── Reports ─────────────────────────────────────────────
export const fetchReports = () =>
  api.get('/reports/').then(r => r.data);

export const generateReport = (incidentId, formats) =>
  api.post('/reports/generate', { incident_id: incidentId, formats }).then(r => r.data);

export const getReportDownloadUrl = (reportId, format) =>
  `${API_BASE}/reports/download/${reportId}?format=${format}`;

export default api;

