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
  const params = useParams();
  const username = params.shareId;
  const { loading, error, analysisData, analyzeProfile } = useAnalysisContext();
  const [loadingMessage, setLoadingMessage] = useState<string>('Analyzing GitHub profile...');

  useEffect(() => {
    if (username) {
      setLoadingMessage(`Analyzing GitHub profile for ${username}...`);
      analyzeProfile(username);
    }
  }, [username, analyzeProfile]);

  if (loading) {
    return <LoadingOverlay message={loadingMessage} />;
  }

  if (error) {
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

  return (
    <Container maxWidth="lg" sx={{ mt: 8 }}>
      <AnalysisResults data={analysisData} isSharedView={true} />
    </Container>
  );
};

export default SharedAnalysisView; 