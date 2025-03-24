import React, { useEffect } from 'react';
import { Box, CssBaseline, ThemeProvider } from '@mui/material';
import { BrowserRouter, Route, Routes, useLocation } from 'react-router-dom';
import { theme } from './styles/theme';
import Header from './components/layout/Header';
import LandingPage from './components/analysis/LandingPage';
import SharedAnalysisView from './components/analysis/SharedAnalysisView';
import { AnalysisProvider } from './contexts/AnalysisContext';
import { AuthProvider } from './contexts/AuthContext';
import { initAnalytics, trackPageView } from './utils/analytics';
import CookieConsent from './components/common/CookieConsent';

// Track page views component
const PageTracker = () => {
  const location = useLocation();
  
  useEffect(() => {
    trackPageView(location.pathname + location.search);
  }, [location]);
  
  return null;
};

// Main app content with analytics tracking
const AppContent = () => {
  return (
    <Box display="flex" flexDirection="column" minHeight="100vh">
      <Header />
      <PageTracker />
      <Box component="main" flexGrow={1}>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/shared/:shareId" element={<SharedAnalysisView />} />
        </Routes>
      </Box>
    </Box>
  );
};

function App() {
  useEffect(() => {
    initAnalytics();
  }, []);

  return (
    <AuthProvider>
      <AnalysisProvider>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <BrowserRouter>
            <AppContent />
          </BrowserRouter>
          <CookieConsent />
        </ThemeProvider>
      </AnalysisProvider>
    </AuthProvider>
  );
}

export default App; 