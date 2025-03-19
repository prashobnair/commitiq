import React from 'react';
import { Box, Typography, Avatar } from '@mui/material';

interface PrintHeaderProps {
  username: string;
  avatarUrl?: string;
  name?: string;
  overallRating: string;
}

/**
 * Header component for the print/PDF view
 */
const PrintHeader: React.FC<PrintHeaderProps> = ({ 
  username, 
  avatarUrl, 
  name, 
  overallRating 
}) => {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 4 }}>
      <Box sx={{ display: 'flex', alignItems: 'center' }}>
        {avatarUrl && (
          <Avatar 
            src={avatarUrl} 
            alt={username}
            sx={{ 
              width: 64, 
              height: 64, 
              mr: 2,
              border: '2px solid #5271ff'
            }}
          />
        )}
        <Typography variant="h4" component="h1" sx={{ fontWeight: 'bold' }}>
          {username}
        </Typography>
      </Box>
      <Typography 
        variant="subtitle1"
        sx={{ 
          color: 'text.secondary',
          alignSelf: 'center'
        }}
      >
        {overallRating}
      </Typography>
    </Box>
  );
};

export default PrintHeader; 