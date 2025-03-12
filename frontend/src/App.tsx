import React from 'react';
import { ThemeProvider, CssBaseline } from '@mui/material';
import { theme } from './styles/theme';
import Header from './components/layout/Header';
import LandingPage from './components/analysis/LandingPage';

const App: React.FC = () => {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Header />
      <LandingPage />
    </ThemeProvider>
  );
};

export default App; 