import React from 'react';
import { Box, CircularProgress, Typography, useTheme } from '@mui/material';

interface Props {
  message?: string;
}

const LoadingOverlay: React.FC<Props> = ({ message = 'Analyzing GitHub profile...' }) => {
  const theme = useTheme();

  return (
    <Box
      sx={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        zIndex: theme.zIndex.modal,
        gap: 2,
      }}
    >
      <CircularProgress size={60} thickness={4} />
      <Typography variant="h6" color="textSecondary">
        {message}
      </Typography>
    </Box>
  );
};

export default LoadingOverlay; 