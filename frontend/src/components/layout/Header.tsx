import React from 'react';
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
import { Assessment, GitHub } from '@mui/icons-material';

const Header: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  return (
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
            {!isMobile && (
              <>
                <Button color="inherit">How It Works</Button>
                <Button color="inherit">Pricing</Button>
                <Button color="inherit">About</Button>
              </>
            )}
            <Button
              variant="contained"
              color="primary"
              startIcon={<GitHub />}
              sx={{ whiteSpace: 'nowrap' }}
            >
              {isMobile ? 'Sign In' : 'Sign In with GitHub'}
            </Button>
          </Box>
        </Toolbar>
      </Container>
    </AppBar>
  );
};

export default Header; 