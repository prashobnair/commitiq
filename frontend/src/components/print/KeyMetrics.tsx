import React from 'react';
import { Box, Typography, Grid, Paper } from '@mui/material';

interface KeyMetricsProps {
  pulls: number;
  issues: number;
  reviews: number;
  commits: number;
  consistency: number;
  repoImpact: number;
}

/**
 * Key Metrics component for the print/PDF view
 * Displays important metrics in a grid layout
 */
const KeyMetrics: React.FC<KeyMetricsProps> = ({
  pulls,
  issues,
  reviews,
  commits,
  consistency,
  repoImpact
}) => {
  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Key Metrics
      </Typography>
      
      <Paper elevation={0} sx={{ p: 3, borderRadius: 2, bgcolor: '#f9f9f9' }}>
        <Grid container spacing={3}>
          {/* Pull Requests */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Pull Requests
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {pulls}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Collaborative contributions
              </Typography>
            </Box>
          </Grid>
          
          {/* Issues */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Issues
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {issues}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Problem identification
              </Typography>
            </Box>
          </Grid>
          
          {/* Code Reviews */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Code Reviews
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {reviews}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Code quality feedback
              </Typography>
            </Box>
          </Grid>
          
          {/* Commits */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Commits
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {commits}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Code contributions
              </Typography>
            </Box>
          </Grid>
          
          {/* Consistency */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Consistency
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {(consistency * 100).toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Active days ratio
              </Typography>
            </Box>
          </Grid>
          
          {/* Repository Impact */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Repo Impact
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {(repoImpact * 100).toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Project significance
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

export default KeyMetrics; 