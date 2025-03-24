import React, { useState, useEffect } from 'react';
import { Box, Button, Snackbar, Typography, Link } from '@mui/material';

const CookieConsent: React.FC = () => {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    // Check if user has already consented
    const hasConsented = localStorage.getItem('cookieConsent') === 'true';
    if (!hasConsented) {
      setOpen(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cookieConsent', 'true');
    setOpen(false);
  };

  return (
    <Snackbar
      open={open}
      anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      sx={{
        '& .MuiSnackbarContent-root': {
          width: '100%',
          maxWidth: { xs: '90%', sm: '600px' }
        }
      }}
    >
      <Box
        sx={{
          bgcolor: 'background.paper',
          p: 2,
          borderRadius: 1,
          boxShadow: 3,
          border: '1px solid',
          borderColor: 'divider',
          display: 'flex',
          flexDirection: { xs: 'column', sm: 'row' },
          alignItems: { xs: 'flex-start', sm: 'center' },
          justifyContent: 'space-between',
          gap: 2
        }}
      >
        <Typography variant="body2" color="text.primary">
          We use cookies and similar technologies to provide essential services, analyze site traffic, and enhance user experience. 
          By using CommitIQ, you consent to our use of cookies in accordance with our{' '}
          <Link href="/privacy-policy" target="_blank" rel="noopener">
            Privacy Policy
          </Link>
          .
        </Typography>
        <Button
          variant="contained"
          size="small"
          color="primary"
          onClick={handleAccept}
          sx={{ whiteSpace: 'nowrap' }}
        >
          Accept
        </Button>
      </Box>
    </Snackbar>
  );
};

export default CookieConsent; 