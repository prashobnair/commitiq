import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Container,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import { Assessment } from '@mui/icons-material';
import WaitingListModal from '../common/WaitingListModal';

const Header: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const [waitingListOpen, setWaitingListOpen] = useState(false);

  const openWaitingList = () => {
    setWaitingListOpen(true);
  };

  const closeWaitingList = () => {
    setWaitingListOpen(false);
  };

  return (
    <>
      <AppBar position="fixed" color="default" elevation={1}>
        <Container maxWidth="xl">
          <Toolbar disableGutters>
            <Assessment sx={{ mr: 1, color: theme.palette.primary.main }} />
            <Typography
              variant="h6"
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

            <Box sx={{ display: 'flex', gap: 2 }}>
              <Button
                variant="contained"
                color="primary"
                onClick={openWaitingList}
                sx={{ whiteSpace: 'nowrap' }}
              >
                {isMobile ? 'Join List' : 'Join Waiting List'}
              </Button>
            </Box>
          </Toolbar>
        </Container>
      </AppBar>
      <WaitingListModal open={waitingListOpen} onClose={closeWaitingList} />
    </>
  );
};

export default Header; 