import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material';
import { useParams, Link as RouterLink } from 'react-router-dom';
import AnalysisResults from './AnalysisResults';
import LoadingOverlay from '../common/LoadingOverlay';
import { useAnalysisContext } from '../../contexts/AnalysisContext';

const SharedAnalysisView: React.FC = () => {
  console.log('[SharedAnalysisView] Component mounted');
  
  const params = useParams();
  const username = params.shareId;
  console.log('[SharedAnalysisView] Extracted username from URL:', username);
  
  const { loading, error, analysisData, analyzeProfile } = useAnalysisContext();
  const [loadingMessage, setLoadingMessage] = useState<string>('Analyzing GitHub profile...');

  useEffect(() => {
    if (username) {
      console.log('[SharedAnalysisView] Starting analysis for username:', username);
      setLoadingMessage(`Analyzing GitHub profile for ${username}...`);
      //analyzeProfile(username);
      analyzeProfile(username)
        .then(() => {
          console.log('[SharedAnalysisView] Analysis completed successfully');
        })
        .catch((err) => {
          console.error('[SharedAnalysisView] Analysis failed:', err);
        });
    }
  }, [username, analyzeProfile]);

  if (loading) {
    console.log('[SharedAnalysisView] Rendering loading state');
    return <LoadingOverlay message={loadingMessage} />;
  }

  if (error) {
    console.log('[SharedAnalysisView] Rendering error state:', error);
    return (
      <Container maxWidth="lg">
        <Box sx={{ my: 8 }}>
          <Alert severity="error" sx={{ mb: 3 }}>
            {error}
          </Alert>
          <Button
            component={RouterLink}
            to="/"
            variant="contained"
            color="primary"
          >
            Return to Home
          </Button>
        </Box>
      </Container>
    );
  }

  if (!analysisData) {
    console.log('[SharedAnalysisView] No analysis data found for username:', username);
    return (
      <Container maxWidth="lg">
        <Box sx={{ my: 8 }}>
          <Alert severity="warning" sx={{ mb: 3 }}>
            No analysis data found for user: {username}
          </Alert>
          <Button
            component={RouterLink}
            to="/"
            variant="contained"
            color="primary"
          >
            Return to Home
          </Button>
        </Box>
      </Container>
    );
  }

  console.log('[SharedAnalysisView] Rendering analysis results');
  return (
    <Container maxWidth="lg" sx={{ mt: 8 }}>
      <AnalysisResults data={analysisData} isSharedView={true} />
    </Container>
  );
};

export default SharedAnalysisView; 