import React from 'react';
import { useQuery } from 'react-query';
import {
  Box,
  Typography,
  Grid,
  Paper,
  CircularProgress,
  Chip,
} from '@mui/material';
import { getSystemHealth } from '../services/api';

function ServicesPage() {
  const { data: health, isLoading } = useQuery('systemHealth', getSystemHealth);

  if (isLoading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
      </Box>
    );
  }

  const getStatusColor = (status) => {
    return status === 'UP' ? 'success' : 'error';
  };

  const services = ['service-a', 'service-b', 'service-c', 'ml-service', 'fuzzy-engine', 'ontology-mapper'];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Services Health
      </Typography>

      <Grid container spacing={3}>
        {services.map((service) => {
          const serviceHealth = health?.[service];
          return (
            <Grid item xs={12} sm={6} md={4} key={service}>
              <Paper sx={{ p: 3 }}>
                <Typography variant="h6" gutterBottom>
                  {service}
                </Typography>
                {serviceHealth && (
                  <Box>
                    <Chip
                      label={serviceHealth.status}
                      color={getStatusColor(serviceHealth.status)}
                      sx={{ mb: 2 }}
                    />
                    {serviceHealth.details && (
                      <Box mt={2}>
                        <Typography variant="caption" color="text.secondary">
                          Details
                        </Typography>
                        <pre style={{ fontSize: '0.75rem', overflow: 'auto' }}>
                          {JSON.stringify(serviceHealth.details, null, 2)}
                        </pre>
                      </Box>
                    )}
                  </Box>
                )}
              </Paper>
            </Grid>
          );
        })}
      </Grid>
    </Box>
  );
}

export default ServicesPage;
