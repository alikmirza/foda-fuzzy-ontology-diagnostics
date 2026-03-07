import React from 'react';
import { useQuery } from 'react-query';
import {
  Grid,
  Paper,
  Typography,
  Box,
  CircularProgress,
  Alert,
  Chip,
} from '@mui/material';
import {
  CheckCircle as HealthyIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
} from '@mui/icons-material';
import { getSystemHealth, getRecentDiagnostics, getFaultStatistics } from '../services/api';

function Dashboard() {
  const { data: health, isLoading: healthLoading } = useQuery('systemHealth', getSystemHealth);
  const { data: diagnostics, isLoading: diagLoading } = useQuery('recentDiagnostics', () => getRecentDiagnostics(5));
  const { data: stats, isLoading: statsLoading } = useQuery('faultStatistics', getFaultStatistics);

  if (healthLoading || diagLoading || statsLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const getStatusColor = (status) => {
    if (status === 'UP') return 'success';
    if (status === 'DEGRADED') return 'warning';
    return 'error';
  };

  const getStatusIcon = (status) => {
    if (status === 'UP') return <HealthyIcon />;
    if (status === 'DEGRADED') return <WarningIcon />;
    return <ErrorIcon />;
  };

  const getSeverityColor = (severity) => {
    const colors = {
      'Low': 'info',
      'Medium': 'warning',
      'High': 'error',
      'Critical': 'error',
    };
    return colors[severity] || 'default';
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        System Dashboard
      </Typography>

      <Grid container spacing={3}>
        {/* System Health Overview */}
        <Grid item xs={12}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              System Health
            </Typography>
            {health && (
              <Box>
                <Box display="flex" alignItems="center" mb={2}>
                  <Chip
                    icon={getStatusIcon(health.overallStatus)}
                    label={health.overallStatus}
                    color={getStatusColor(health.overallStatus)}
                    sx={{ mr: 2 }}
                  />
                  <Typography variant="caption" color="text.secondary">
                    Last updated: {new Date(health.timestamp).toLocaleString()}
                  </Typography>
                </Box>
                <Grid container spacing={2}>
                  {Object.entries(health).map(([key, value]) => {
                    if (key === 'overallStatus' || key === 'timestamp' || typeof value !== 'object') return null;
                    return (
                      <Grid item xs={12} sm={6} md={4} key={key}>
                        <Box p={1} border={1} borderColor="divider" borderRadius={1}>
                          <Typography variant="subtitle2" color="text.secondary">
                            {key}
                          </Typography>
                          <Chip
                            size="small"
                            label={value.status}
                            color={getStatusColor(value.status)}
                          />
                        </Box>
                      </Grid>
                    );
                  })}
                </Grid>
              </Box>
            )}
          </Paper>
        </Grid>

        {/* Recent Diagnostics */}
        <Grid item xs={12} md={8}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Recent Diagnostics
            </Typography>
            {diagnostics && diagnostics.length > 0 ? (
              <Box>
                {diagnostics.map((diag, index) => (
                  <Box
                    key={index}
                    p={2}
                    mb={1}
                    border={1}
                    borderColor="divider"
                    borderRadius={1}
                  >
                    <Grid container spacing={2} alignItems="center">
                      <Grid item xs={12} sm={3}>
                        <Typography variant="subtitle2" color="text.secondary">
                          Service
                        </Typography>
                        <Typography variant="body2">{diag.serviceId}</Typography>
                      </Grid>
                      <Grid item xs={12} sm={3}>
                        <Typography variant="subtitle2" color="text.secondary">
                          Fault Type
                        </Typography>
                        <Typography variant="body2">
                          {diag.faultType?.replace(/.*#/, '')}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} sm={2}>
                        <Typography variant="subtitle2" color="text.secondary">
                          Severity
                        </Typography>
                        <Chip
                          size="small"
                          label={diag.severity}
                          color={getSeverityColor(diag.severity)}
                        />
                      </Grid>
                      <Grid item xs={12} sm={2}>
                        <Typography variant="subtitle2" color="text.secondary">
                          FCI
                        </Typography>
                        <Typography variant="body2">
                          {parseFloat(diag.fci).toFixed(3)}
                        </Typography>
                      </Grid>
                      <Grid item xs={12} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          {new Date(diag.timestamp).toLocaleTimeString()}
                        </Typography>
                      </Grid>
                    </Grid>
                  </Box>
                ))}
              </Box>
            ) : (
              <Alert severity="info">No recent diagnostics</Alert>
            )}
          </Paper>
        </Grid>

        {/* Fault Statistics */}
        <Grid item xs={12} md={4}>
          <Paper sx={{ p: 2 }}>
            <Typography variant="h6" gutterBottom>
              Fault Statistics
            </Typography>
            {stats && stats.length > 0 ? (
              <Box>
                {stats.slice(0, 5).map((stat, index) => (
                  <Box
                    key={index}
                    display="flex"
                    justifyContent="space-between"
                    alignItems="center"
                    p={1}
                    mb={1}
                    border={1}
                    borderColor="divider"
                    borderRadius={1}
                  >
                    <Typography variant="body2">
                      {stat.faultType?.replace(/.*#/, '')}
                    </Typography>
                    <Chip size="small" label={stat.count} color="primary" />
                  </Box>
                ))}
              </Box>
            ) : (
              <Alert severity="info">No fault statistics available</Alert>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

export default Dashboard;
