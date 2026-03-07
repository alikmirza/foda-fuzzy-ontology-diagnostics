import React, { useState } from 'react';
import { useQuery } from 'react-query';
import {
  Box,
  Typography,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  CircularProgress,
  TextField,
  MenuItem,
} from '@mui/material';
import { getRecentDiagnostics, getDiagnosticsBySeverity } from '../services/api';

function DiagnosticsPage() {
  const [severity, setSeverity] = useState('all');

  const { data: diagnostics, isLoading } = useQuery(
    ['diagnostics', severity],
    () => severity === 'all' ? getRecentDiagnostics(50) : getDiagnosticsBySeverity(severity)
  );

  const getSeverityColor = (sev) => {
    const colors = { 'Low': 'info', 'Medium': 'warning', 'High': 'error', 'Critical': 'error' };
    return colors[sev] || 'default';
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Diagnostic History
      </Typography>

      <Paper sx={{ p: 2, mb: 2 }}>
        <TextField
          select
          label="Filter by Severity"
          value={severity}
          onChange={(e) => setSeverity(e.target.value)}
          sx={{ minWidth: 200 }}
        >
          <MenuItem value="all">All Severities</MenuItem>
          <MenuItem value="Low">Low</MenuItem>
          <MenuItem value="Medium">Medium</MenuItem>
          <MenuItem value="High">High</MenuItem>
          <MenuItem value="Critical">Critical</MenuItem>
        </TextField>
      </Paper>

      {isLoading ? (
        <Box display="flex" justifyContent="center" p={4}>
          <CircularProgress />
        </Box>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Diagnostic ID</TableCell>
                <TableCell>Service</TableCell>
                <TableCell>Fault Type</TableCell>
                <TableCell>Severity</TableCell>
                <TableCell>FCI</TableCell>
                <TableCell>Timestamp</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {diagnostics?.map((diag, index) => (
                <TableRow key={index}>
                  <TableCell>{diag.diagnosticId?.substring(0, 8)}...</TableCell>
                  <TableCell>{diag.serviceId}</TableCell>
                  <TableCell>{diag.faultType?.replace(/.*#/, '')}</TableCell>
                  <TableCell>
                    <Chip size="small" label={diag.severity} color={getSeverityColor(diag.severity)} />
                  </TableCell>
                  <TableCell>{parseFloat(diag.fci).toFixed(3)}</TableCell>
                  <TableCell>{new Date(diag.timestamp).toLocaleString()}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
}

export default DiagnosticsPage;
