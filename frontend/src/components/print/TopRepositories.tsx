import React from 'react';
import { Box, Typography, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper } from '@mui/material';

interface Repository {
  name: string;
  stars?: number;
  forks?: number;
  primary_language?: string | null;
}

interface TopRepositoriesProps {
  repositories: Repository[];
}

/**
 * Top Repositories component for the print/PDF view
 * Displays the developer's most significant repositories
 */
const TopRepositories: React.FC<TopRepositoriesProps> = ({ repositories }) => {
  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Top Repositories
      </Typography>
      
      <TableContainer component={Paper} elevation={0}>
        <Table>
          <TableHead sx={{ backgroundColor: '#5271ff' }}>
            <TableRow>
              <TableCell sx={{ color: 'white', fontWeight: 'bold' }}>Repository</TableCell>
              <TableCell align="center" sx={{ color: 'white', fontWeight: 'bold' }}>Stars</TableCell>
              <TableCell align="center" sx={{ color: 'white', fontWeight: 'bold' }}>Forks</TableCell>
              <TableCell align="center" sx={{ color: 'white', fontWeight: 'bold' }}>Language</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {repositories.map((repo, index) => (
              <TableRow key={index} sx={{ backgroundColor: index % 2 === 0 ? '#f8f9fa' : 'white' }}>
                <TableCell component="th" scope="row">
                  {repo.name}
                </TableCell>
                <TableCell align="center">{repo.stars || 0}</TableCell>
                <TableCell align="center">{repo.forks || 0}</TableCell>
                <TableCell align="center">{repo.primary_language || 'N/A'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default TopRepositories; 