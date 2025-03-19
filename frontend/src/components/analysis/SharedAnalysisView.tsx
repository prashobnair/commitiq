import React, { useState, useEffect } from 'react';
import {
  Box,
  Container,
  Typography,
  CircularProgress,
  Alert,
  Button,
  Divider,
  Paper,
  Card,
  CardContent,
  Grid,
} from '@mui/material';
import { Share, Download, Assessment } from '@mui/icons-material';
import { useParams, Link as RouterLink } from 'react-router-dom';
import AnalysisResults from './AnalysisResults';
import { API_BASE_URL } from '../../config';
import ShareOptions from './ShareOptions';

// Use type for router params
type SharedAnalysisParams = {
  shareId: string;
};

interface SharedAnalysisData {
  share_info: {
    share_id: string;
    created_at: string;
    expires_at: string | null;
    access_count: number;
  };
  analysis: any;
}

const SharedAnalysisView: React.FC = () => {
  // Use useParams without type parameter for React Router v6
  const params = useParams();
  const shareId = params.shareId;
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<SharedAnalysisData | null>(null);

  useEffect(() => {
    const fetchSharedAnalysis = async () => {
      setLoading(true);
      try {
        const response = await fetch(`${API_BASE_URL}/api/share/view/${shareId}`);
        
        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Shared analysis not found. The link may be invalid.');
          } else if (response.status === 410) {
            throw new Error('This shared analysis has expired.');
          } else {
            throw new Error('Failed to load shared analysis.');
          }
        }
        
        const result = await response.json();
        setData(result);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An unknown error occurred');
      } finally {
        setLoading(false);
      }
    };

    if (shareId) {
      fetchSharedAnalysis();
    } else {
      setError('No share ID provided');
      setLoading(false);
    }
  }, [shareId]);

  if (loading) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ my: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <CircularProgress size={60} sx={{ mb: 3 }} />
          <Typography variant="h6">Loading shared analysis...</Typography>
        </Box>
      </Container>
    );
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

  if (!data) {
    return (
      <Container maxWidth="lg">
        <Box sx={{ my: 8 }}>
          <Alert severity="warning" sx={{ mb: 3 }}>
            No analysis data found.
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

  // Get the analysis ID for download functionality
  const analysisId = data.analysis.id || 0;
  const githubUsername = data.analysis.github_username || '';

  return (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Card sx={{ mb: 4, borderRadius: 2 }}>
          <CardContent>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
              <Typography variant="h5" component="h1">
                Shared GitHub Analysis
              </Typography>
              <Box>
                <Typography variant="caption" color="text.secondary">
                  Viewed {data.share_info.access_count} times
                </Typography>
              </Box>
            </Box>
            
            <Divider sx={{ mb: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={12} md={8}>
                <Typography variant="body1">
                  <strong>Developer:</strong> {githubUsername}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  <strong>Shared:</strong> {new Date(data.share_info.created_at).toLocaleDateString()}
                </Typography>
              </Grid>
              <Grid item xs={12} md={4} sx={{ display: 'flex', justifyContent: { xs: 'flex-start', md: 'flex-end' } }}>
                {data.share_info.expires_at && (
                  <Typography variant="body2" color="warning.main">
                    Expires: {new Date(data.share_info.expires_at).toLocaleDateString()}
                  </Typography>
                )}
              </Grid>
            </Grid>
          </CardContent>
        </Card>
        
        {/* Allow sharing and downloading this analysis */}
        <Box sx={{ mb: 4, display: 'flex', justifyContent: 'center' }}>
          <ShareOptions analysisId={analysisId} githubUsername={githubUsername} />
        </Box>
        
        {/* Analysis Results */}
        <AnalysisResults data={data.analysis} />
        
        {/* Footer with attribution */}
        <Box sx={{ mt: 6, mb: 3, textAlign: 'center' }}>
          <Divider sx={{ mb: 3 }} />
          <Typography variant="body2" color="text.secondary">
            Analysis provided by CommitIQ - Technical Recruiting, Reinvented
          </Typography>
          <Button
            component={RouterLink}
            to="/"
            size="small"
            startIcon={<Assessment />}
            sx={{ mt: 2 }}
          >
            Analyze Your Own Profile
          </Button>
        </Box>
      </Box>
    </Container>
  );
};

export default SharedAnalysisView; 