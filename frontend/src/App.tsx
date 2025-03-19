import React from 'react';
import { Box, CssBaseline, ThemeProvider } from '@mui/material';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { theme } from './styles/theme';
import Header from './components/layout/Header';
import LandingPage from './components/analysis/LandingPage';
import SharedAnalysisView from './components/analysis/SharedAnalysisView';
import { AnalysisProvider } from './contexts/AnalysisContext';
import { AuthProvider } from './contexts/AuthContext';

function App() {
  return (
    <AuthProvider>
      <AnalysisProvider>
        <ThemeProvider theme={theme}>
          <CssBaseline />
          <BrowserRouter>
            <Box display="flex" flexDirection="column" minHeight="100vh">
              <Header />
              <Box component="main" flexGrow={1}>
                <Routes>
                  <Route path="/" element={<LandingPage />} />
                  <Route path="/shared/:shareId" element={<SharedAnalysisView />} />
                </Routes>
              </Box>
            </Box>
          </BrowserRouter>
        </ThemeProvider>
      </AnalysisProvider>
    </AuthProvider>
  );
}

export default App; 