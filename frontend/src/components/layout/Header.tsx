import React, { useState, useEffect } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Container,
  useTheme,
  useMediaQuery,
  Badge,
  Tooltip,
} from '@mui/material';
import WaitingListModal from '../common/WaitingListModal';
import logoSrc from '../../logo.svg';
import { useAnalysisContext } from '../../contexts/AnalysisContext';

// API URL from environment variables
const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:5000/api';

interface WaitlistCountResponse {
  count: number;
  message: string;
  error?: string;
}

const Header: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [waitingListOpen, setWaitingListOpen] = useState(false);
  const [waitlistCount, setWaitlistCount] = useState<number | null>(null);
  const [waitlistMessage, setWaitlistMessage] = useState<string>('');
  const { resetAnalysis } = useAnalysisContext();
  
  // Function to handle logo click - reset analysis to return to search
  const handleLogoClick = () => {
    resetAnalysis();
    console.log('Logo clicked, resetting analysis');
  };
  
  // Fetch waiting list count when component mounts
  useEffect(() => {
    const fetchWaitlistCount = async () => {
      try {
        const response = await fetch(`${API_URL}/waitlist/count`);
        if (!response.ok) {
          throw new Error('Failed to fetch waiting list count');
        }
        
        const data: WaitlistCountResponse = await response.json();
        setWaitlistCount(data.count);
        setWaitlistMessage(data.message);
      } catch (error) {
        console.error('Error fetching waitlist count:', error);
      }
    };
    
    fetchWaitlistCount();
  }, []);

  const openWaitingList = () => {
    setWaitingListOpen(true);
  };

  const closeWaitingList = () => {
    setWaitingListOpen(false);
    // Refresh the count when modal is closed
    fetchWaitlistCount();
  };
  
  // Function to fetch waitlist count (for refreshing after modal closes)
  const fetchWaitlistCount = async () => {
    try {
      const response = await fetch(`${API_URL}/waitlist/count`);
      if (!response.ok) {
        throw new Error('Failed to fetch waiting list count');
      }
      
      const data: WaitlistCountResponse = await response.json();
      setWaitlistCount(data.count);
      setWaitlistMessage(data.message);
    } catch (error) {
      console.error('Error fetching waitlist count:', error);
    }
  };

  return (
    <>
      <AppBar position="fixed" color="default" elevation={1}>
        <Container maxWidth="xl">
          <Toolbar disableGutters>
            <Box 
              onClick={handleLogoClick}
              sx={{ 
                display: 'flex', 
                alignItems: 'center', 
                cursor: 'pointer',
                '&:hover': {
                  opacity: 0.8
                }
              }}
            >
              <img 
                src={logoSrc} 
                alt="CommitIQ Logo" 
                style={{ height: '40px', width: 'auto', marginRight: '8px' }} 
              />
              <Typography
                variant="h4"
                noWrap
                component="div"
                sx={{
                  flexGrow: 1,
                  display: 'flex',
                  alignItems: 'center',
                  color: theme.palette.primary.main,
                  fontWeight: 600,
                }}
              >
                CommitIQ
              </Typography>
            </Box>

            <Box sx={{ flexGrow: 1 }} />

            <Box sx={{ display: 'flex', gap: 2 }}>
              <Tooltip title={waitlistMessage} arrow>
                <Badge 
                  badgeContent={waitlistCount} 
                  color="primary"
                  max={999}
                  sx={{ 
                    '& .MuiBadge-badge': { 
                      fontSize: '0.75rem',
                      fontWeight: 'bold',
                      right: -3,
                      top: 13,
                    } 
                  }}
                >
                  <Button
                    variant="contained"
                    color="primary"
                    onClick={openWaitingList}
                    sx={{ whiteSpace: 'nowrap' }}
                  >
                    {isMobile ? 'Join List' : 'Join Waiting List'}
                  </Button>
                </Badge>
              </Tooltip>
            </Box>
          </Toolbar>
        </Container>
      </AppBar>
      <WaitingListModal open={waitingListOpen} onClose={closeWaitingList} />
    </>
  );
};

export default Header; 