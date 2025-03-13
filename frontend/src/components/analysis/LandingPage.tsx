import React, { useState } from 'react';
import {
  Box,
  Container,
  Typography,
  TextField,
  Button,
  Paper,
  Grid,
  useTheme,
  alpha,
  CircularProgress,
  Card,
  Divider,
  Stack,
  Avatar,
} from '@mui/material';
import {
  TrendingUp,
  Psychology,
  Timeline,
  GitHub,
  CompareArrows,
  Speed,
  People,
} from '@mui/icons-material';
import AnalysisResults from './AnalysisResults';
import LoadingOverlay from '../common/LoadingOverlay';
import useGitHubAnalysis from '../../hooks/useGitHubAnalysis';

const LandingPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const { loading, error, analysisData, analyzeProfile, resetAnalysis } = useGitHubAnalysis();
  const theme = useTheme();

  const handleAnalyze = () => {
    if (username.trim()) {
      analyzeProfile(username);
    }
  };

  const features = [
    {
      icon: <TrendingUp />,
      title: 'Impact Score',
      description: 'Comprehensive evaluation of developer contributions and influence',
    },
    {
      icon: <Psychology />,
      title: 'Deep Insights',
      description: 'Advanced metrics beyond commit counts and green squares',
    },
    {
      icon: <Timeline />,
      title: 'Growth Tracking',
      description: 'Track developer progress and evolution over time',
    },
  ];

  const benefits = [
    {
      icon: <Speed />,
      title: 'Faster Hiring',
      description: 'Quickly identify top talent based on real contributions',
    },
    {
      icon: <CompareArrows />,
      title: 'Objective Comparison',
      description: 'Compare candidates using standardized metrics',
    },
    {
      icon: <People />,
      title: 'Team Fit',
      description: 'Assess collaboration style and team compatibility',
    },
  ];

  if (analysisData) {
    return (
      <Container maxWidth="lg" sx={{ mt: 8 }}>
        <Button
          variant="outlined"
          color="primary"
          onClick={resetAnalysis}
          sx={{ mb: 4 }}
        >
          ← Back to Search
        </Button>
        <AnalysisResults data={analysisData} />
      </Container>
    );
  }

  return (
    <>
      {loading && <LoadingOverlay />}
      <Box
        sx={{
          minHeight: '100vh',
          background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(
            theme.palette.secondary.main,
            0.1
          )} 100%)`,
        }}
      >
        {/* Hero Section */}
        <Box
          sx={{
            pt: { xs: 10, sm: 15 },
            pb: { xs: 8, sm: 12 },
            background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.9)} 0%, ${alpha(
              theme.palette.secondary.main,
              0.8
            )} 100%)`,
            color: 'white',
            position: 'relative',
            overflow: 'hidden',
          }}
        >
          {/* Background Elements */}
          <Box
            sx={{
              position: 'absolute',
              top: -100,
              right: -100,
              width: 400,
              height: 400,
              borderRadius: '50%',
              background: alpha('#fff', 0.05),
              zIndex: 0,
            }}
          />
          <Box
            sx={{
              position: 'absolute',
              bottom: -150,
              left: -150,
              width: 300,
              height: 300,
              borderRadius: '50%',
              background: alpha('#fff', 0.05),
              zIndex: 0,
            }}
          />

          <Container maxWidth="lg" sx={{ position: 'relative', zIndex: 1 }}>
            <Grid container spacing={4} alignItems="center">
              <Grid item xs={12} md={7}>
                <Typography
                  variant="h1"
                  component="h1"
                  sx={{
                    fontWeight: 800,
                    fontSize: { xs: '2.5rem', md: '3.5rem' },
                    mb: 2,
                    textShadow: '0 2px 10px rgba(0,0,0,0.1)',
                  }}
                >
                  Discover True Developer Impact
                </Typography>
                <Typography
                  variant="h5"
                  sx={{ 
                    mb: 4, 
                    fontWeight: 400,
                    opacity: 0.9,
                    maxWidth: '600px',
                  }}
                >
                  Beyond the green squares - Get deep insights into developer contributions
                  and impact through advanced GitHub analytics
                </Typography>

                <Paper
                  elevation={4}
                  sx={{
                    p: 0.5,
                    maxWidth: '600px',
                    display: 'flex',
                    gap: 1,
                    borderRadius: 3,
                    background: 'white',
                    boxShadow: '0 8px 20px rgba(0,0,0,0.1)',
                  }}
                >
                  <TextField
                    fullWidth
                    placeholder="Enter GitHub username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    error={!!error}
                    helperText={error}
                    disabled={loading}
                    onKeyPress={(e) => e.key === 'Enter' && handleAnalyze()}
                    InputProps={{
                      startAdornment: <GitHub color="action" sx={{ mr: 1, color: theme.palette.primary.main }} />,
                    }}
                    sx={{ 
                      '& .MuiOutlinedInput-notchedOutline': { border: 'none' },
                      '& .MuiInputBase-root': { pl: 1 },
                    }}
                  />
                  <Button
                    variant="contained"
                    color="primary"
                    size="large"
                    onClick={handleAnalyze}
                    disabled={loading || !username.trim()}
                    sx={{ 
                      px: 4,
                      borderRadius: 2,
                      fontWeight: 600,
                    }}
                  >
                    {loading ? <CircularProgress size={24} color="inherit" /> : 'Analyze'}
                  </Button>
                </Paper>

                
              </Grid>
              <Grid item xs={12} md={5} sx={{ display: { xs: 'none', md: 'block' } }}>
                <Box
                  sx={{
                    position: 'relative',
                    height: '400px',
                    width: '100%',
                  }}
                >
                  <Box
                    sx={{
                      position: 'absolute',
                      top: '10%',
                      left: '5%',
                      width: '90%',
                      height: '80%',
                      borderRadius: 4,
                      background: alpha(theme.palette.background.paper, 0.9),
                      boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
                      p: 3,
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <Avatar sx={{ bgcolor: theme.palette.primary.main, mr: 2 }}>JD</Avatar>
                      <Box>
                        <Typography variant="h6" sx={{ color: theme.palette.text.primary }}>
                          John Doe
                        </Typography>
                        <Typography variant="body2" sx={{ color: theme.palette.text.secondary }}>
                          Senior Developer
                        </Typography>
                      </Box>
                    </Box>
                    <Box
                      sx={{
                        height: 10,
                        borderRadius: 5,
                        background: `linear-gradient(90deg, ${theme.palette.success.main} 0%, ${theme.palette.warning.main} 50%, ${theme.palette.error.main} 100%)`,
                        mb: 3,
                      }}
                    />
                    <Grid container spacing={2}>
                      {[
                        { label: 'Impact Score', value: '87.5' },
                        { label: 'Code Quality', value: '92.3' },
                        { label: 'Collaboration', value: '78.9' },
                        { label: 'Consistency', value: '85.2' },
                      ].map((metric, index) => (
                        <Grid item xs={6} key={index}>
                          <Paper
                            sx={{
                              p: 2,
                              textAlign: 'center',
                              background: alpha(theme.palette.background.default, 0.7),
                            }}
                          >
                            <Typography variant="body2" color="textSecondary">
                              {metric.label}
                            </Typography>
                            <Typography variant="h5" color="primary" sx={{ fontWeight: 'bold' }}>
                              {metric.value}
                            </Typography>
                          </Paper>
                        </Grid>
                      ))}
                    </Grid>
                  </Box>
                </Box>
              </Grid>
            </Grid>
          </Container>
        </Box>

        <Container maxWidth="lg">
          {/* Features Section */}
          <Box sx={{ py: 8 }}>
            <Typography
              variant="h2"
              component="h2"
              align="center"
              sx={{ mb: 1, fontWeight: 700 }}
            >
              Why CommitIQ?
            </Typography>
            <Typography
              variant="h6"
              align="center"
              color="textSecondary"
              sx={{ mb: 6, maxWidth: '700px', mx: 'auto' }}
            >
              Our platform provides recruiters with deep insights into developer skills and impact
            </Typography>

            <Grid container spacing={4}>
              {features.map((feature, index) => (
                <Grid item xs={12} md={4} key={index}>
                  <Card
                    elevation={0}
                    sx={{
                      p: 3,
                      height: '100%',
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 3,
                      transition: 'all 0.3s ease',
                      '&:hover': {
                        borderColor: theme.palette.primary.main,
                        transform: 'translateY(-8px)',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
                      },
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        mb: 2,
                      }}
                    >
                      <Avatar
                        sx={{
                          bgcolor: alpha(theme.palette.primary.main, 0.1),
                          color: theme.palette.primary.main,
                          mr: 2,
                        }}
                      >
                        {feature.icon}
                      </Avatar>
                      <Typography variant="h5" sx={{ fontWeight: 600 }}>
                        {feature.title}
                      </Typography>
                    </Box>
                    <Typography color="textSecondary" variant="body1">
                      {feature.description}
                    </Typography>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>

          <Divider sx={{ my: 4 }} />

          {/* Benefits Section */}
          <Box sx={{ py: 8 }}>
            <Typography
              variant="h2"
              component="h2"
              align="center"
              sx={{ mb: 1, fontWeight: 700 }}
            >
              Benefits for Recruiters
            </Typography>
            <Typography
              variant="h6"
              align="center"
              color="textSecondary"
              sx={{ mb: 6, maxWidth: '700px', mx: 'auto' }}
            >
              Make better hiring decisions with objective data-driven insights
            </Typography>

            <Grid container spacing={4}>
              {benefits.map((benefit, index) => (
                <Grid item xs={12} md={4} key={index}>
                  <Card
                    elevation={0}
                    sx={{
                      p: 3,
                      height: '100%',
                      border: `1px solid ${theme.palette.divider}`,
                      borderRadius: 3,
                      transition: 'all 0.3s ease',
                      '&:hover': {
                        borderColor: theme.palette.secondary.main,
                        transform: 'translateY(-8px)',
                        boxShadow: '0 10px 30px rgba(0,0,0,0.1)',
                      },
                    }}
                  >
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        mb: 2,
                      }}
                    >
                      <Avatar
                        sx={{
                          bgcolor: alpha(theme.palette.secondary.main, 0.1),
                          color: theme.palette.secondary.main,
                          mr: 2,
                        }}
                      >
                        {benefit.icon}
                      </Avatar>
                      <Typography variant="h5" sx={{ fontWeight: 600 }}>
                        {benefit.title}
                      </Typography>
                    </Box>
                    <Typography color="textSecondary" variant="body1">
                      {benefit.description}
                    </Typography>
                  </Card>
                </Grid>
              ))}
            </Grid>
          </Box>

          {/* CTA Section */}
          <Box sx={{ py: 8, textAlign: 'center' }}>
            <Card
              sx={{
                p: 6,
                borderRadius: 4,
                background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.05)} 0%, ${alpha(
                  theme.palette.secondary.main,
                  0.1
                )} 100%)`,
                border: `1px solid ${theme.palette.divider}`,
              }}
            >
              <Typography variant="h3" component="h3" sx={{ mb: 2, fontWeight: 700 }}>
                Ready to transform your technical recruiting?
              </Typography>
              <Typography
                variant="h6"
                color="textSecondary"
                sx={{ mb: 4, maxWidth: '700px', mx: 'auto' }}
              >
                Start analyzing GitHub profiles today and discover the true impact of your candidates
              </Typography>
              <Button
                variant="contained"
                color="primary"
                size="large"
                startIcon={<GitHub />}
                sx={{ px: 4, py: 1.5, borderRadius: 2, fontWeight: 600 }}
              >
                Sign Up for Free
              </Button>
            </Card>
          </Box>
        </Container>
      </Box>
    </>
  );
};

export default LandingPage; 