import React, { useEffect, useState, lazy } from 'react';
import { useRouter } from '../../utils/nextShims';
import { Box, Container, Typography, CircularProgress, Paper, Grid } from '@mui/material';
import { API_BASE_URL } from '../../config';
import { AnalysisResponse, Analysis, Contributions } from '../../types/analysis';
import { Head } from '../../utils/nextShims';

// Dynamic imports for print components to avoid module resolution issues
const PrintHeader = lazy(() => import('../../components/print/PrintHeader'));
const OverallImpactScore = lazy(() => import('../../components/print/OverallImpactScore'));
const DeveloperSummary = lazy(() => import('../../components/print/DeveloperSummary'));
const KeyInsights = lazy(() => import('../../components/print/KeyInsights'));
// Define inline KeyMetrics component instead of importing
interface KeyMetricsProps {
  pulls: number;
  issues: number;
  reviews: number;
  commits: number;
  consistency: number;
  repoImpact: number;
}

const KeyMetrics: React.FC<KeyMetricsProps> = ({
  pulls,
  issues,
  reviews,
  commits,
  consistency,
  repoImpact
}) => {
  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Key Metrics
      </Typography>
      
      <Paper elevation={0} sx={{ p: 3, borderRadius: 2, bgcolor: '#f9f9f9' }}>
        <Grid container spacing={3}>
          {/* Pull Requests */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Pull Requests
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {pulls}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Collaborative contributions
              </Typography>
            </Box>
          </Grid>
          
          {/* Issues */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Issues
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {issues}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Problem identification
              </Typography>
            </Box>
          </Grid>
          
          {/* Code Reviews */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Code Reviews
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {reviews}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Code quality feedback
              </Typography>
            </Box>
          </Grid>
          
          {/* Commits */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Commits
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {commits}
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Code contributions
              </Typography>
            </Box>
          </Grid>
          
          {/* Consistency */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Consistency
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {(consistency * 100).toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Active days ratio
              </Typography>
            </Box>
          </Grid>
          
          {/* Repository Impact */}
          <Grid item xs={6} md={4}>
            <Box sx={{ textAlign: 'center' }}>
              <Typography variant="overline" color="textSecondary" display="block">
                Repo Impact
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {(repoImpact * 100).toFixed(1)}%
              </Typography>
              <Typography variant="body2" color="textSecondary">
                Project significance
              </Typography>
            </Box>
          </Grid>
        </Grid>
      </Paper>
    </Box>
  );
};

const TopLanguages = lazy(() => import('../../components/print/TopLanguages'));
const TopRepositories = lazy(() => import('../../components/print/TopRepositories'));
const PrintFooter = lazy(() => import('../../components/print/PrintFooter'));

/**
 * Print-friendly page for GitHub analysis results
 * This page is designed to be rendered by Puppeteer for PDF generation
 */
const PrintPage: React.FC = () => {
  const router = useRouter();
  const { username: usernameParam, id } = router.query;
  
  const [loading, setLoading] = useState<boolean>(true);
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  useEffect(() => {
    // Only fetch data when we have both username and id
    if (!usernameParam || !id) return;
    
    const fetchAnalysis = async () => {
      try {
        // Use the analysis ID if provided, otherwise fetch by username
        const response = await fetch(`${API_BASE_URL}/api/analysis/${id}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch analysis: ${response.statusText}`);
        }
        
        const data = await response.json();
        setAnalysis(data);
      } catch (err) {
        console.error('Error fetching analysis:', err);
        setError('Failed to load analysis data');
      } finally {
        setLoading(false);
      }
    };
    
    fetchAnalysis();
  }, [usernameParam, id]);
  
  if (loading) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          justifyContent: 'center', 
          alignItems: 'center', 
          minHeight: '100vh' 
        }}
      >
        <CircularProgress />
      </Box>
    );
  }
  
  if (error || !analysis) {
    return (
      <Box 
        sx={{ 
          display: 'flex', 
          flexDirection: 'column',
          justifyContent: 'center', 
          alignItems: 'center', 
          minHeight: '100vh' 
        }}
      >
        <Typography variant="h5" color="error" gutterBottom>
          {error || 'Analysis not found'}
        </Typography>
        <Typography variant="body1">
          Unable to generate PDF for this analysis.
        </Typography>
      </Box>
    );
  }
  
  // Extract data needed for the report
  const { 
    impact_score = 0,
    analysis: analysisData = {} as Analysis
  } = analysis || {} as AnalysisResponse;
  
  const username = analysisData?.username || '';
  const name = analysisData?.name || '';
  const avatarUrl = analysisData?.avatarUrl || '';
  const contributions = analysisData?.contributions || {} as Contributions;
  
  const {
    commits = 0,
    pulls = 0,
    issues = 0,
    reviews = 0,
    consistency = 0,
    repos_impact = 0,
    top_languages = [],
    top_repositories = []
  } = contributions;
  
  // Determine overall rating based on impact score
  const getOverallRating = (score: number) => {
    if (score <= 40) return 'Developing Contributor';
    if (score <= 50) return 'Solid Contributor';
    if (score <= 60) return 'Above Average Contributor';
    if (score <= 70) return 'Strong Contributor';
    return 'Exceptional Contributor';
  };
  
  const overallRating = getOverallRating(impact_score);
  
  // Calculate strengths and considerations
  const calculateStrengths = () => {
    const strengths = [];
    
    if (pulls > 30) {
      strengths.push('High number of pull requests, indicating strong collaboration');
    }
    
    const consistencyPercent = consistency * 100;
    if (consistency > 0.7) {
      strengths.push(`Excellent consistency (${consistencyPercent.toFixed(1)}% active days)`);
    }
    
    if (reviews > 20) {
      strengths.push('Frequent code reviews, showing willingness to provide feedback');
    }
    
    if (commits > 200) {
      strengths.push('Significant number of commits, demonstrating active development');
    }
    
    // Ensure we have at least one strength
    if (strengths.length === 0) {
      strengths.push('Shows engagement with GitHub projects');
    }
    
    return strengths;
  };
  
  const calculateConsiderations = () => {
    const considerations = [];
    
    if (repos_impact < 0.03) {
      considerations.push('Lower repository impact score—contributions may be in less popular repos');
    }
    
    if (pulls < 10 && commits > 100) {
      considerations.push('High commits but low PRs may indicate solo work rather than collaboration');
    }
    
    if (consistency < 0.5) {
      considerations.push('Inconsistent contribution pattern may indicate sporadic engagement');
    }
    
    // Add a neutral consideration if none exist
    if (considerations.length === 0) {
      considerations.push('No significant concerns identified in the contribution pattern');
    }
    
    return considerations;
  };
  
  const strengths = calculateStrengths();
  const considerations = calculateConsiderations();
  
  return (
    <>
      <Head>
        <title>GitHub Analysis for {username} | CommitIQ</title>
        <meta name="robots" content="noindex" />
        <style>{`
          @media print {
            @page {
              size: letter;
              margin: 0;
            }
            body, html {
              margin: 0;
              padding: 0;
              width: 100%;
              height: auto !important;
              overflow: visible !important;
              -webkit-print-color-adjust: exact !important;
              print-color-adjust: exact !important;
              color-adjust: exact !important;
            }
            .page-break {
              page-break-before: always;
            }
            .print-section, .print-container {
              display: block !important;
              visibility: visible !important;
              opacity: 1 !important;
              height: auto !important;
              overflow: visible !important;
              position: relative !important;
              page-break-inside: avoid;
            }
            .background-gradient, [class*='gradient'] {
              -webkit-print-color-adjust: exact !important;
              print-color-adjust: exact !important;
              color-adjust: exact !important;
            }
          }
          
          body {
            background: white;
          }
        `}</style>
      </Head>
      
      <Box 
        className="print-container"
        sx={{ 
          width: '100%',
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          bgcolor: '#ffffff'
        }}
      >
        {/* Background gradient wrapper */}
        <Box
          className="background-gradient print-section"
          sx={{
            background: 'linear-gradient(to right, #5271ff, #0fe3a2)',
            minHeight: '100vh',
            pt: 4,
            pb: 8
          }}
        >
          <Container maxWidth="md" className="print-container">
            <Paper
              elevation={0}
              className="print-section"
              sx={{
                p: 4,
                borderRadius: 2,
                bgcolor: 'white',
                overflow: 'hidden'
              }}
            >
              {/* Print Header */}
              <React.Suspense fallback={<div className="print-section">Loading header...</div>}>
                <Box className="print-section" data-testid="header-section">
                  <PrintHeader 
                    username={username}
                    avatarUrl={avatarUrl}
                    name={name}
                    overallRating={overallRating}
                  />
                </Box>
              </React.Suspense>
              
              {/* Overall Impact Score */}
              <React.Suspense fallback={<div className="print-section">Loading overall impact score...</div>}>
                <Box className="print-section" data-testid="impact-score-section">
                  <OverallImpactScore 
                    score={impact_score}
                    rating={overallRating}
                  />
                </Box>
              </React.Suspense>
              
              {/* Developer Summary */}
              <React.Suspense fallback={<div className="print-section">Loading developer summary...</div>}>
                <Box className="print-section" data-testid="developer-summary-section">
                  <DeveloperSummary 
                    username={username}
                    name={name}
                    commits={commits}
                    pulls={pulls}
                    consistency={consistency}
                    reviews={reviews}
                  />
                </Box>
              </React.Suspense>
              
              {/* Key Insights */}
              <React.Suspense fallback={<div className="print-section">Loading key insights...</div>}>
                <Box className="print-section" data-testid="insights-section">
                  <KeyInsights 
                    strengths={strengths}
                    considerations={considerations}
                  />
                </Box>
              </React.Suspense>
              
              {/* Key Metrics */}
              <React.Suspense fallback={<div className="print-section">Loading metrics...</div>}>
                <Box className="print-section" data-testid="metrics-section">
                  <KeyMetrics 
                    pulls={pulls}
                    issues={issues}
                    reviews={reviews}
                    commits={commits}
                    consistency={consistency}
                    repoImpact={repos_impact}
                  />
                </Box>
              </React.Suspense>
              
              {/* Top Languages */}
              {top_languages && top_languages.length > 0 && (
                <Box className="print-section" data-testid="languages-section">
                  <TopLanguages languages={top_languages} />
                </Box>
              )}
              
              {/* Top Repositories */}
              {top_repositories && top_repositories.length > 0 && (
                <Box className="print-section" data-testid="repositories-section">
                  <TopRepositories repositories={top_repositories.map((repo: any) => ({
                    name: repo.name,
                    stars: repo.stars,
                    forks: repo.forks,
                    primary_language: repo.primaryLanguage || repo.primary_language || 'N/A'
                  }))} />
                </Box>
              )}
              
              {/* Footer */}
              <React.Suspense fallback={<div className="print-section">Loading footer...</div>}>
                <Box className="print-section" data-testid="footer-section">
                  <PrintFooter />
                </Box>
              </React.Suspense>
            </Paper>
          </Container>
        </Box>
      </Box>
    </>
  );
};

export default PrintPage; 