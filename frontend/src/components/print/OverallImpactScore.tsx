import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

interface OverallImpactScoreProps {
  score: number;
  rating: string;
}

/**
 * Overall Impact Score component for the print/PDF view
 */
const OverallImpactScore: React.FC<OverallImpactScoreProps> = ({ score, rating }) => {
  return (
    <Paper
      elevation={0}
      sx={{
        mb: 4,
        p: 3,
        borderRadius: 2,
        backgroundColor: '#f8f9fa',
      }}
    >
      <Typography variant="h6" gutterBottom>
        Overall Impact Score
      </Typography>
      
      <Box sx={{ textAlign: 'center', my: 2 }}>
        <Typography 
          variant="h2" 
          sx={{ 
            color: '#5271ff',
            fontWeight: 'bold',
            lineHeight: 1.2
          }}
        >
          {score.toFixed(1)}
        </Typography>
        
        <Typography 
          variant="subtitle1" 
          sx={{ color: 'text.secondary', mt: 1 }}
        >
          {rating}
        </Typography>
      </Box>
      
      <Typography variant="body2" color="text.secondary">
        This score represents the developer's overall impact based on contributions, collaboration, consistency, and project influence.
      </Typography>
    </Paper>
  );
};

export default OverallImpactScore; 