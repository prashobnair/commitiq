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
  LinearProgress,
  Chip,
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
      description: 'Measure a developer\'s true contributions and influence beyond commit counts',
    },
    {
      icon: <Psychology />,
      title: 'Deep Insights',
      description: 'Understand technical expertise, collaboration habits, and consistency with advanced metrics',
    },
    {
      icon: <Timeline />,
      title: 'Growth Tracking',
      description: 'Track a developer\'s progress over time and identify those with a strong track record of improvement and learning',
    },
  ];

  const benefits = [
    {
      icon: <Speed />,
      title: 'Faster Hiring',
      description: 'Quickly filter out top candidates from hundreds of profiles based on actual contributions',
    },
    {
      icon: <CompareArrows />,
      title: 'Objective Comparison',
      description: 'Use standardized metrics to compare developers fairly and efficiently',
    },
    {
      icon: <People />,
      title: 'Team Fit',
      description: 'Evaluate collaboration style and engagement to ensure cultural and workflow compatibility',
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
                  Identify Top Engineering Talent Instantly
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
                  Go beyond green squares—leverage advanced GitHub analytics to pinpoint the most impactful developers in your candidate pool
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
                    height: '420px',
                    width: '100%',
                  }}
                >
                  <Box
                    sx={{
                      position: 'absolute',
                      top: '5%',
                      left: '-10%',
                      width: '120%',
                      height: '90%',
                      borderRadius: 4,
                      background: alpha(theme.palette.background.paper, 0.95),
                      boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
                      p: 2.5,
                      display: 'flex',
                      flexDirection: 'column',
                      overflow: 'hidden',
                    }}
                  >
                    {/* Developer Profile Header */}
                    <Box sx={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      mb: 1.5,
                      p: 1.5,
                      borderRadius: 2,
                      background: `linear-gradient(135deg, ${alpha(theme.palette.primary.main, 0.8)} 0%, ${alpha(theme.palette.secondary.main, 0.8)} 100%)`,
                      color: 'white',
                    }}>
                      <Avatar sx={{ bgcolor: 'white', color: theme.palette.primary.main, mr: 2, width: 40, height: 40 }}>JD</Avatar>
                      <Box>
                        <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
                          John Doe
                        </Typography>
                        <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>
                          Strong Contributor
                        </Typography>
                      </Box>
                    </Box>

                    {/* Main Content */}
                    <Box sx={{ 
                      display: 'flex', 
                      flexDirection: 'row',
                      gap: 2.5,
                      flex: 1,
                      overflow: 'hidden'
                    }}>
                      {/* Left Column - Impact Score and Top Languages */}
                      <Box sx={{ 
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 2,
                        width: '50%'
                      }}>
                        {/* Impact Score */}
                        <Card sx={{ 
                          borderRadius: 2,
                          background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
                          color: 'white',
                          flex: 6,
                          p: 1.5
                        }}>
                          <Typography variant="subtitle2" fontWeight="bold">
                            Overall Impact Score
                          </Typography>
                          <Box sx={{ display: 'flex', alignItems: 'center', my: 1 }}>
                            <Typography variant="h4" component="div" sx={{ fontWeight: 'bold', mr: 1.5 }}>
                              78.5
                            </Typography>
                            <Box sx={{ flexGrow: 1 }}>
                              <LinearProgress
                                variant="determinate"
                                value={78.5}
                                sx={{
                                  height: 8,
                                  borderRadius: 3,
                                  backgroundColor: 'rgba(255,255,255,0.2)',
                                  '& .MuiLinearProgress-bar': {
                                    backgroundColor: 'white',
                                  },
                                }}
                              />
                              <Typography variant="body2" sx={{ mt: 0.5, fontWeight: 'medium', fontSize: '0.75rem' }}>
                                Strong Contributor
                              </Typography>
                            </Box>
                          </Box>
                        </Card>
                        
                        {/* Top Languages */}
                        <Card sx={{ 
                          borderRadius: 2,
                          flex: 4,
                          p: 1.5
                        }}>
                          <Typography variant="subtitle2" fontWeight="bold">
                            Top Languages
                          </Typography>
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.8, mt: 1 }}>
                            {[
                              { language: 'TypeScript', percentage: 0.45 },
                              { language: 'JavaScript', percentage: 0.30 },
                              { language: 'Vue', percentage: 0.15 },
                              { language: 'Go', percentage: 0.10 }
                            ].map((lang, index) => (
                              <Chip
                                key={index}
                                label={`${lang.language}: ${(lang.percentage * 100).toFixed(0)}%`}
                                size="small"
                                sx={{
                                  bgcolor: `${theme.palette.primary.main}15`,
                                  color: theme.palette.primary.main,
                                  fontSize: '0.7rem',
                                  height: 22,
                                  fontWeight: 'medium'
                                }}
                              />
                            ))}
                          </Box>
                        </Card>
                      </Box>

                      {/* Right Column - Developer Summary */}
                      <Box sx={{ width: '50%' }}>
                        <Card sx={{ 
                          height: '100%', 
                          borderRadius: 2,
                          p: 1.5,
                          display: 'flex',
                          flexDirection: 'column'
                        }}>
                          <Typography variant="subtitle2" fontWeight="bold">
                            Developer Summary
                          </Typography>
                          <Typography variant="body2" sx={{ display: 'block', mt: 1, mb: 1, fontSize: '0.8rem' }}>
                            John has made 356 commits and 87 PRs with 42 code reviews, showing strong collaboration and consistent activity.
                          </Typography>
                          
                          <Box sx={{ 
                            display: 'flex', 
                            flexDirection: 'column', 
                            gap: 1,
                            mt: 'auto',
                            mb: 0.5
                          }}>
                            <Box>
                              <Typography variant="body2" fontWeight="bold" sx={{ fontSize: '0.8rem' }}>
                                Strengths
                              </Typography>
                              
                              <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                                <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: 'success.main', mr: 1.5, flexShrink: 0 }} />
                                <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>Excellent consistency (76.2% active days)</Typography>
                              </Box>
                            </Box>
                            
                            <Box>
                              <Typography variant="body2" fontWeight="bold" sx={{ fontSize: '0.8rem' }}>
                                Considerations
                              </Typography>
                              <Box sx={{ display: 'flex', alignItems: 'center', mt: 0.5 }}>
                                <Box sx={{ width: 7, height: 7, borderRadius: '50%', bgcolor: 'warning.main', mr: 1.5, flexShrink: 0 }} />
                                <Typography variant="body2" sx={{ fontSize: '0.8rem' }}>Primarily focused on frontend technologies</Typography>
                              </Box>
                            </Box>
                          </Box>
                        </Card>
                      </Box>
                    </Box>
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
              Our platform helps recruiters quickly identify and prioritize high-potential candidates based on real-world contributions, collaboration, and technical influence
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
               Supercharge Your Tech Hiring Process
              </Typography>
              <Typography
                variant="h6"
                color="textSecondary"
                sx={{ mb: 4, maxWidth: '700px', mx: 'auto' }}
              >
                Start analyzing GitHub profiles today and uncover the developers who will make the biggest impact on your team
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