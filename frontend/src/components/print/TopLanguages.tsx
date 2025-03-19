import React from 'react';
import { Box, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';

interface Language {
  name?: string;
  language?: string;
  percentage?: number;
  percent?: number;
}

interface TopLanguagesProps {
  languages: Language[];
}

/**
 * Top Languages component for the print/PDF view
 * Displays the developer's most used programming languages
 */
const TopLanguages: React.FC<TopLanguagesProps> = ({ languages }) => {
  // Format languages data for display
  const formattedLanguages = languages.map(lang => {
    const name = lang.name || lang.language || 'Unknown';
    
    // Check if percentage is already in percentage format (> 1) or decimal format (< 1)
    let percentage = 0;
    if ('percentage' in lang && lang.percentage !== undefined) {
      percentage = lang.percentage;
      if (percentage <= 1) {
        percentage *= 100;
      }
    } else if ('percent' in lang && lang.percent !== undefined) {
      percentage = lang.percent;
      if (percentage <= 1) {
        percentage *= 100;
      }
    }
    
    return {
      name,
      percentage
    };
  });
  
  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Top Languages
      </Typography>
      
      <TableContainer component={Paper} elevation={0}>
        <Table>
          <TableHead sx={{ backgroundColor: '#5271ff' }}>
            <TableRow>
              <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Language</TableCell>
              <TableCell align="right" sx={{ color: 'white', fontWeight: 'bold' }}>Percentage</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {formattedLanguages.map((lang, index) => (
              <TableRow key={index} sx={{ backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                <TableCell component="th" scope="row">
                  {lang.name}
                </TableCell>
                <TableCell align="right">{lang.percentage.toFixed(1)}%</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default TopLanguages; 