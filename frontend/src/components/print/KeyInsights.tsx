import React from 'react';
import { Box, Typography, Grid, Paper, List, ListItem, ListItemIcon, ListItemText } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined';

interface KeyInsightsProps {
  strengths: string[];
  considerations: string[];
}

/**
 * Key Insights component for the print/PDF view
 * Displays strengths and considerations in a two-column layout
 */
const KeyInsights: React.FC<KeyInsightsProps> = ({ strengths, considerations }) => {
  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Key Insights
      </Typography>
      
      <Grid container spacing={3}>
        {/* Strengths */}
        <Grid item xs={12} md={6}>
          <Typography 
            variant="subtitle1" 
            sx={{ 
              color: '#28a745',
              fontWeight: 'bold',
              mb: 1 
            }}
          >
            Strengths
          </Typography>
          
          <List dense disablePadding>
            {strengths.map((strength, index) => (
              <ListItem key={index} disableGutters sx={{ mb: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 24, color: '#28a745' }}>
                  <CheckCircleOutlineIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={strength} />
              </ListItem>
            ))}
          </List>
        </Grid>
        
        {/* Considerations */}
        <Grid item xs={12} md={6}>
          <Typography 
            variant="subtitle1" 
            sx={{ 
              color: '#dc3545',
              fontWeight: 'bold',
              mb: 1 
            }}
          >
            Considerations
          </Typography>
          
          <List dense disablePadding>
            {considerations.map((consideration, index) => (
              <ListItem key={index} disableGutters sx={{ mb: 0.5 }}>
                <ListItemIcon sx={{ minWidth: 24, color: '#dc3545' }}>
                  <InfoOutlinedIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText primary={consideration} />
              </ListItem>
            ))}
          </List>
        </Grid>
      </Grid>
    </Box>
  );
};

export default KeyInsights; 