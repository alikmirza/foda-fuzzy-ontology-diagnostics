import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Dashboard APIs
export const getDashboardOverview = () =>
  api.get('/dashboard/overview').then(res => res.data);

export const getSystemHealth = () =>
  api.get('/dashboard/health').then(res => res.data);

// Ontology APIs
export const getRecentDiagnostics = (limit = 10) =>
  api.get(`/ontology/diagnostics/recent?limit=${limit}`).then(res => res.data);

export const getDiagnosticsByService = (serviceId) =>
  api.get(`/ontology/diagnostics/service/${serviceId}`).then(res => res.data);

export const getDiagnosticsByFault = (faultType) =>
  api.get(`/ontology/diagnostics/fault/${faultType}`).then(res => res.data);

export const getDiagnosticsBySeverity = (severity) =>
  api.get(`/ontology/diagnostics/severity/${severity}`).then(res => res.data);

export const getDiagnosticDetails = (diagnosticId) =>
  api.get(`/ontology/diagnostics/${diagnosticId}`).then(res => res.data);

export const getRecommendations = (diagnosticId) =>
  api.get(`/ontology/diagnostics/${diagnosticId}/recommendations`).then(res => res.data);

export const getContributingFactors = (diagnosticId) =>
  api.get(`/ontology/diagnostics/${diagnosticId}/factors`).then(res => res.data);

export const getFaultStatistics = () =>
  api.get('/ontology/statistics/faults').then(res => res.data);

// Service APIs
export const getServiceStatus = (serviceId) => {
  const serviceMap = {
    'service-a': '/services/service-a/status',
    'service-b': '/services/service-b/status',
    'service-c': '/services/service-c/status',
  };
  return api.get(serviceMap[serviceId] || `/services/${serviceId}/status`).then(res => res.data);
};

export const getServiceMetrics = (serviceId) => {
  const serviceMap = {
    'service-a': '/services/service-a/metrics',
    'service-b': '/services/service-b/metrics',
    'service-c': '/services/service-c/metrics',
  };
  return api.get(serviceMap[serviceId] || `/services/${serviceId}/metrics`).then(res => res.data);
};

export default api;
