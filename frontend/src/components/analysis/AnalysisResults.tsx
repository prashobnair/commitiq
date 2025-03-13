import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Chip,
  LinearProgress,
  Avatar,
  Link,
  useTheme,
  Divider,
  Tooltip,
  Button,
  Paper,
  Stack,
} from '@mui/material';
import {
  Code,
  MergeType,
  BugReport,
  RateReview,
  Commit,
  TrendingUp,
  GitHub,
  CalendarMonth,
  Download,
  Share,
  Person,
  Star,
  BarChart,
  Code as CodeIcon,
} from '@mui/icons-material';
import { AnalysisResponse, MetricCard, Repository, Contributions } from '../../types/analysis';

interface Props {
  data: AnalysisResponse;
}

// Helper function to determine rating based on value
const getRating = (value: number, type: string): { label: string; color: string } => {
  // These thresholds should be adjusted based on your data distribution
  switch (type) {
    case 'prs':
      if (value > 50) return { label: 'High', color: 'success.main' };
      if (value > 20) return { label: 'Above Average', color: 'success.light' };
      if (value > 10) return { label: 'Moderate', color: 'warning.main' };
      return { label: 'Low', color: 'error.light' };
    
    case 'issues':
      if (value > 50) return { label: 'High', color: 'success.main' };
      if (value > 20) return { label: 'Above Average', color: 'success.light' };
      if (value > 10) return { label: 'Moderate', color: 'warning.main' };
      return { label: 'Low', color: 'error.light' };
    
    case 'reviews':
      if (value > 30) return { label: 'High', color: 'success.main' };
      if (value > 15) return { label: 'Above Average', color: 'success.light' };
      if (value > 5) return { label: 'Moderate', color: 'warning.main' };
      return { label: 'Low', color: 'error.light' };
    
    case 'commits':
      if (value > 300) return { label: 'High', color: 'success.main' };
      if (value > 100) return { label: 'Above Average', color: 'success.light' };
      if (value > 50) return { label: 'Moderate', color: 'warning.main' };
      return { label: 'Low', color: 'error.light' };
    
    case 'consistency':
      if (value > 0.8) return { label: 'Excellent', color: 'success.main' };
      if (value > 0.6) return { label: 'Good', color: 'success.light' };
      if (value > 0.4) return { label: 'Moderate', color: 'warning.main' };
      return { label: 'Inconsistent', color: 'error.light' };
    
    case 'impact':
      if (value > 0.05) return { label: 'High', color: 'success.main' };
      if (value > 0.03) return { label: 'Above Average', color: 'success.light' };
      if (value > 0.01) return { label: 'Moderate', color: 'warning.main' };
      return { label: 'Low', color: 'error.light' };
    
    default:
      return { label: 'Moderate', color: 'warning.main' };
  }
};

// Helper function to get color from theme based on color string
const getColorFromTheme = (theme: any, colorString: string): string => {
  if (!colorString) return theme.palette.primary.main;
  
  const [palette, shade] = colorString.split('.');
  if (palette && shade && theme.palette[palette] && theme.palette[palette][shade]) {
    return theme.palette[palette][shade];
  }
  
  return theme.palette.primary.main;
};

// Default empty contributions object with all values set to 0
const emptyContributions: Contributions = {
  pulls: 0,
  commits: 0,
  consistency: 0,
  reviews: 0,
  issues: 0,
  repos_impact: 0,
  top_languages: [],
  top_repositories: []
};

// Helper function to generate a summary of the developer's profile
const generateSummary = (data: AnalysisResponse): string => {
  // Extract contribution data from the correct location in the response
  const contributions = data.analysis.contributions || emptyContributions;
  const pulls = contributions.pulls;
  const commits = contributions.commits;
  const consistency = contributions.consistency;
  const reviews = contributions.reviews;
  
  // Get developer name or username
  const developerName = data.analysis.name || data.analysis.username;
  
  const prRating = getRating(pulls, 'prs');
  const commitRating = getRating(commits, 'commits');
  const consistencyRating = getRating(consistency, 'consistency');
  
  return `${developerName} has made ${commits} commits and ${pulls} pull requests, showing ${prRating.label.toLowerCase()} collaboration. Their consistency is ${(consistency * 100).toFixed(1)}%, indicating ${consistencyRating.label.toLowerCase()} regular activity. With ${reviews} code reviews, they actively engage in code discussions. Overall, they're a ${commitRating.label.toLowerCase()} contributor who ${pulls > 30 ? 'frequently' : 'occasionally'} participates in various projects.`;
};

// Helper function to determine overall rating
const getOverallRating = (score: number): string => {
  if (score > 80) return 'Exceptional Contributor';
  if (score > 70) return 'Strong Contributor';
  if (score > 60) return 'Above Average Contributor';
  if (score > 50) return 'Solid Contributor';
  if (score > 40) return 'Moderate Contributor';
  return 'Developing Contributor';
};

// Helper function to identify strengths and considerations
const getStrengthsAndConsiderations = (data: AnalysisResponse): { strengths: string[], considerations: string[] } => {
  // Extract contribution data from the correct location in the response
  const contributions = data.analysis.contributions || emptyContributions;
  const pulls = contributions.pulls;
  const commits = contributions.commits;
  const consistency = contributions.consistency;
  const reviews = contributions.reviews;
  const repos_impact = contributions.repos_impact;
  
  const strengths: string[] = [];
  const considerations: string[] = [];
  
  // Analyze strengths
  if (pulls > 30) {
    strengths.push('High number of pull requests, indicating strong collaboration');
  }
  
  if (consistency > 0.7) {
    strengths.push(`Excellent consistency (${(consistency * 100).toFixed(1)}% active days)`);
  }
  
  if (reviews > 20) {
    strengths.push('Frequent code reviews, showing willingness to provide feedback');
  }
  
  if (commits > 200) {
    strengths.push('Significant number of commits, demonstrating active development');
  }
  
  // Analyze considerations
  if (repos_impact < 0.03) {
    considerations.push('Lower repository impact score—contributions may be in less popular repos');
  }
  
  if (pulls < 10 && commits > 100) {
    considerations.push('High commits but low PRs may indicate solo work rather than collaboration');
  }
  
  if (consistency < 0.5) {
    considerations.push('Inconsistent contribution pattern may indicate sporadic engagement');
  }
  
  // Ensure we have at least one strength
  if (strengths.length === 0) {
    strengths.push('Shows engagement with GitHub projects');
  }
  
  // If no considerations, add a neutral one
  if (considerations.length === 0) {
    considerations.push('No significant concerns identified in the contribution pattern');
  }
  
  return { strengths, considerations };
};

// Helper function to format date string
const formatDate = (dateString: string | undefined): string => {
  if (!dateString) return 'N/A';
  
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  } catch (e) {
    return 'N/A';
  }
};

// Helper function to map repository data from backend format to our component format
const mapRepositories = (repoData: any[]): Repository[] => {
  if (!repoData || !Array.isArray(repoData) || repoData.length === 0) {
    console.log("No repositories data found");
    return [];
  }
  
  return repoData.map((repo: any) => {
    console.log("Processing repository:", repo);
    
    // Determine the URL to use
    let repoUrl = '#';
    if (repo.homepageUrl) {
      repoUrl = repo.homepageUrl;
    } else if (repo.name) {
      repoUrl = `https://github.com/${repo.name}`;
    }
    
    return {
      name: repo.name || 'Unknown Repository',
      url: repoUrl,
      stars: repo.stars || 0,
      forks: repo.forks || 0,
      num_contributors: repo.collaborators || 0,
      primary_language: repo.primary_language || 'N/A',
      commit_frequency: repo.commit_frequency || 'N/A',
      last_updated: repo.last_commit_date ? formatDate(repo.last_commit_date) : 'N/A',
      num_commits: repo.contribution_ratio ? (repo.contribution_ratio * 100).toFixed(1) + '%' : '0%',
      impact_score: repo.repo_impact || 0
    };
  });
};

const AnalysisResults: React.FC<Props> = ({ data }) => {
  const theme = useTheme();
  console.log("Full analysis data:", JSON.stringify(data, null, 2));

  // Ensure we have valid data
  if (!data || !data.analysis) {
    return (
      <Box sx={{ py: 4 }}>
        <Typography variant="h6" color="error">
          No analysis data available
        </Typography>
      </Box>
    );
  }

  // Extract contribution data from the correct location in the response
  const contributions = data.analysis.contributions || emptyContributions;
  console.log("Contributions data:", JSON.stringify(contributions, null, 2));
  
  const pulls = contributions.pulls;
  const issues = contributions.issues;
  const reviews = contributions.reviews;
  const commits = contributions.commits;
  const consistency = contributions.consistency;
  const repos_impact = contributions.repos_impact;
  
  // Handle different formats of top languages data
  let topLanguages: Array<{ language: string; percentage: number }> = [];
  
  if (contributions.top_languages && Array.isArray(contributions.top_languages)) {
    console.log("Found top_languages in contributions:", contributions.top_languages);
    
    // Map the languages to a consistent format
    topLanguages = contributions.top_languages.map((lang: any) => {
      // Check if the language data is in the expected format
      if (typeof lang === 'object' && lang !== null) {
        // Use name as the primary field, fallback to language if name is not available
        const languageName = lang.name || lang.language || 'Unknown';
        
        // Check if percentage is already in percentage format (> 1) or decimal format (< 1)
        let percentage = 0;
        if (typeof lang.percentage === 'number') {
          percentage = lang.percentage > 1 ? lang.percentage : lang.percentage * 100;
        } else if (typeof lang.percent === 'number') {
          percentage = lang.percent > 1 ? lang.percent : lang.percent * 100;
        }
        
        return {
          language: languageName,
          percentage: percentage / 100 // Store as decimal for consistent handling
        };
      }
      // Default case for any other format
      return { language: 'Unknown', percentage: 0 };
    });
  } else {
    // Try to find languages data in other locations
    try {
      // Safely access potential language data using optional chaining
      const metricsData = data.analysis.metrics as Record<string, any>;
      const languagesData = metricsData?.languages;
      
      if (languagesData && Array.isArray(languagesData)) {
        console.log("Found languages in metrics:", languagesData);
        topLanguages = languagesData.map((lang: any) => {
          const languageName = lang.language || lang.name || 'Unknown';
          
          // Check if percentage is already in percentage format (> 1) or decimal format (< 1)
          let percentage = 0;
          if (typeof lang.percentage === 'number') {
            percentage = lang.percentage > 1 ? lang.percentage : lang.percentage * 100;
          } else if (typeof lang.percent === 'number') {
            percentage = lang.percent > 1 ? lang.percent : lang.percent * 100;
          }
          
          return {
            language: languageName,
            percentage: percentage / 100 // Store as decimal for consistent handling
          };
        });
      }
    } catch (error) {
      console.error("Error processing languages data:", error);
    }
  }
  
  console.log("Processed top languages:", topLanguages);

  // Map repositories from the contributions data
  let repositories: Repository[] = [];
  
  if (contributions.top_repositories && Array.isArray(contributions.top_repositories)) {
    console.log("Using top_repositories from contributions:", contributions.top_repositories);
    repositories = mapRepositories(contributions.top_repositories);
  } else if (data.analysis.metrics && data.analysis.metrics.repositories) {
    // Fallback to metrics.repositories if available
    console.log("Falling back to metrics.repositories");
    repositories = mapRepositories(data.analysis.metrics.repositories);
  } else if (data.analysis.repos && Array.isArray(data.analysis.repos)) {
    // Try to use repos directly if other sources are not available
    console.log("Using repos directly from analysis:", data.analysis.repos);
    repositories = data.analysis.repos;
  }
  
  console.log("Final mapped repositories:", repositories);

  // Generate summary and insights
  const summary = generateSummary(data);
  const overallRating = getOverallRating(data.impact_score || 0);
  const { strengths, considerations } = getStrengthsAndConsiderations(data);

  // Define metrics with context
  const metrics: MetricCard[] = [
    {
      title: 'Pull Requests',
      value: pulls,
      description: 'Collaborative contributions',
      icon: MergeType,
      color: getRating(pulls, 'prs').color,
    },
    {
      title: 'Issues Raised',
      value: issues,
      description: 'Problem identification',
      icon: BugReport,
      color: getRating(issues, 'issues').color,
    },
    {
      title: 'Code Reviews',
      value: reviews,
      description: 'Feedback & mentorship',
      icon: RateReview,
      color: getRating(reviews, 'reviews').color,
    },
    {
      title: 'Total Commits',
      value: commits,
      description: 'Code contributions',
      icon: Commit,
      color: getRating(commits, 'commits').color,
    },
    {
      title: 'Consistency',
      value: `${(consistency * 100).toFixed(1)}%`,
      description: 'Regular activity pattern',
      icon: CalendarMonth,
      color: getRating(consistency, 'consistency').color,
    },
    {
      title: 'Project Impact',
      value: repos_impact,  // Use the raw value instead of formatted string
      displayValue: (repos_impact).toFixed(3),  // Add a display value for rendering
      description: 'Influence on repositories',
      icon: TrendingUp,
      color: getRating(repos_impact, 'impact').color,
    },
  ];

  return (
    <Box sx={{ py: 4 }}>
      <Grid container spacing={3}>
        {/* Developer Profile Header */}
        <Grid item xs={12}>
          <Card sx={{ mb: 3, overflow: 'hidden', borderRadius: 3 }}>
            <Box sx={{ 
              p: 3, 
              display: 'flex', 
              alignItems: 'center',
              background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
              color: 'white',
            }}>
              <Avatar 
                src={data.analysis.avatarUrl}
                sx={{ 
                  width: 80, 
                  height: 80, 
                  mr: 3,
                  bgcolor: 'white',
                  color: theme.palette.primary.main,
                  border: `2px solid ${theme.palette.primary.light}`,
                }}
              >
                {!(data.analysis.avatarUrl) && <Person sx={{ fontSize: 40 }} />}
              </Avatar>
              <Box>
                {data.analysis.name && (
                  <Typography variant="h4" fontWeight="bold">
                    {data.analysis.name}
                  </Typography>
                )}
                <Typography variant={data.analysis.name ? 'h6' : 'h4'} sx={{ opacity: data.analysis.name ? 0.9 : 1, fontWeight: data.analysis.name ? 'normal' : 'bold' }}>
                  {data.analysis.username || 'Developer'}
                </Typography>
                <Typography variant="h6" sx={{ opacity: 0.9, mt: 1 }}>
                  {overallRating}
                </Typography>
              </Box>
            </Box>
          </Card>
        </Grid>

        {/* Left Column - Impact Score and Top Languages */}
        <Grid item xs={12} md={6}>
          <Grid container spacing={3} sx={{ height: '100%' }}>
            {/* Impact Score */}
            <Grid item xs={12}>
              <Card
                sx={{
                  background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
                  color: 'white',
                  position: 'relative',
                  overflow: 'hidden',
                  borderRadius: 3,
                }}
              >
                <CardContent sx={{ position: 'relative', zIndex: 1, p: 3 }}>
                  <Box
                    sx={{
                      display: 'flex',
                      flexDirection: 'column',
                    }}
                  >
                    <Typography variant="h6" fontWeight="bold" gutterBottom>
                      Overall Impact Score
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                      <Typography variant="h2" component="div" sx={{ fontWeight: 'bold', mr: 2 }}>
                        {(data.impact_score || 0).toFixed(1)}
                      </Typography>
                      <Box sx={{ flexGrow: 1 }}>
                        <LinearProgress
                          variant="determinate"
                          value={Math.min(data.impact_score || 0, 100)}
                          sx={{
                            height: 10,
                            borderRadius: 5,
                            backgroundColor: 'rgba(255,255,255,0.2)',
                            '& .MuiLinearProgress-bar': {
                              backgroundColor: 'white',
                            },
                            mb: 1,
                          }}
                        />
                        <Typography variant="body1">
                          {overallRating}
                        </Typography>
                      </Box>
                    </Box>
                    <Divider sx={{ backgroundColor: 'rgba(255,255,255,0.2)', my: 2 }} />
                    <Typography variant="body2">
                      This score represents the developer's overall impact based on contributions, 
                      collaboration, consistency, and project influence.
                    </Typography>
                  </Box>
                </CardContent>
              </Card>
            </Grid>
            
            {/* Top Languages */}
            {topLanguages && topLanguages.length > 0 && (
              <Grid item xs={12}>
                <Card sx={{ borderRadius: 3 }}>
                  <CardContent sx={{ p: 3 }}>
                    <Typography variant="h6" fontWeight="bold" gutterBottom>
                      Top Languages
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {topLanguages.map((lang, index) => (
                        <Chip
                          key={index}
                          label={`${lang.language}: ${(lang.percentage * 100).toFixed(1)}%`}
                          size="small"
                          sx={{
                            bgcolor: `${theme.palette.primary.main}15`,
                            color: theme.palette.primary.main,
                            my: 0.5
                          }}
                        />
                      ))}
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            )}
          </Grid>
        </Grid>

        {/* Right Column - Developer Summary */}
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%', borderRadius: 3 }}>
            <CardContent sx={{ p: 3 }}>
              <Typography variant="h6" fontWeight="bold" gutterBottom>
                Developer Summary
              </Typography>
              <Typography variant="body1" paragraph>
                {summary}
              </Typography>
              
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                Strengths
              </Typography>
              <Box sx={{ mb: 2 }}>
                {strengths.map((strength, index) => (
                  <Box key={index} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        bgcolor: 'success.main',
                        mr: 1.5,
                      }}
                    />
                    <Typography variant="body2">{strength}</Typography>
                  </Box>
                ))}
              </Box>
              
              <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                Considerations
              </Typography>
              <Box>
                {considerations.map((consideration, index) => (
                  <Box key={index} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Box
                      sx={{
                        width: 8,
                        height: 8,
                        borderRadius: '50%',
                        bgcolor: 'warning.main',
                        mr: 1.5,
                      }}
                    />
                    <Typography variant="body2">{consideration}</Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Metrics */}
        <Grid item xs={12}>
          <Typography variant="h5" gutterBottom sx={{ mt: 2, mb: 3, fontWeight: 600 }}>
            Key Metrics
          </Typography>
          <Grid container spacing={3}>
            {metrics.map((metric, index) => (
              <Grid item xs={12} sm={6} md={4} key={index}>
                <Card sx={{ borderRadius: 3 }}>
                  <CardContent>
                    <Box
                      sx={{
                        display: 'flex',
                        alignItems: 'center',
                        mb: 2,
                      }}
                    >
                      <Avatar
                        sx={{
                          bgcolor: metric.color ? `${getColorFromTheme(theme, metric.color)}15` : theme.palette.primary.light,
                          color: metric.color ? getColorFromTheme(theme, metric.color) : theme.palette.primary.main,
                          mr: 2,
                        }}
                      >
                        <metric.icon />
                      </Avatar>
                      <Box>
                        <Typography color="textSecondary" variant="overline">
                          {metric.title}
                        </Typography>
                        <Typography variant="h4" sx={{ fontWeight: 'bold' }}>
                          {metric.displayValue !== undefined ? metric.displayValue : metric.value}
                        </Typography>
                      </Box>
                    </Box>
                    <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography color="textSecondary" variant="body2">
                        {metric.description}
                      </Typography>
                      <Chip 
                        label={getRating(
                          typeof metric.value === 'string' 
                            ? parseFloat(metric.value) / 100 
                            : metric.title.toLowerCase().includes('impact')
                              ? Number(metric.value) // Don't modify impact value
                              : Number(metric.value), 
                          metric.title.toLowerCase().includes('pull') ? 'prs' : 
                          metric.title.toLowerCase().includes('issue') ? 'issues' :
                          metric.title.toLowerCase().includes('review') ? 'reviews' :
                          metric.title.toLowerCase().includes('commit') ? 'commits' :
                          metric.title.toLowerCase().includes('consist') ? 'consistency' :
                          'impact'
                        ).label} 
                        size="small"
                        sx={{ 
                          bgcolor: metric.color ? `${getColorFromTheme(theme, metric.color)}15` : theme.palette.primary.light,
                          color: metric.color ? getColorFromTheme(theme, metric.color) : theme.palette.primary.main,
                        }}
                      />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Grid>

        {/* Repositories */}
        {repositories && repositories.length > 0 ? (
          <Grid item xs={12}>
            <Typography variant="h5" gutterBottom sx={{ mt: 4, mb: 3, fontWeight: 600 }}>
              Top Repository Contributions
            </Typography>
            <Grid container spacing={3}>
              {repositories
                .sort((a, b) => (b.impact_score || 0) - (a.impact_score || 0))
                .slice(0, 4)
                .map((repo, index) => (
                  <Grid item xs={12} md={6} key={index}>
                    <Card sx={{ borderRadius: 3 }}>
                      <CardContent sx={{ p: 3 }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                          <Typography variant="h6" gutterBottom sx={{ fontWeight: 600 }}>
                            <Link
                              href={repo.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              sx={{ textDecoration: 'none' }}
                            >
                              {repo.name}
                            </Link>
                          </Typography>
                          <Chip 
                            label={`Impact: ${(repo.impact_score || 0).toFixed(2)}`}
                            color="primary"
                            size="small"
                          />
                        </Box>
                        
                        <Grid container spacing={2}>
                          <Grid item xs={6} sm={3}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                              <Star sx={{ color: 'warning.main', mb: 1 }} />
                              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                {repo.stars || 0}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                Stars
                              </Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={6} sm={3}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                              <MergeType sx={{ color: 'primary.main', mb: 1 }} />
                              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                {repo.forks || 0}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                Forks
                              </Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={6} sm={3}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                              <Person sx={{ color: 'info.main', mb: 1 }} />
                              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                {repo.num_contributors || 0}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                Collaborators
                              </Typography>
                            </Box>
                          </Grid>
                          <Grid item xs={6} sm={3}>
                            <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                              <Commit sx={{ color: 'success.main', mb: 1 }} />
                              <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                {repo.num_commits || '0%'}
                              </Typography>
                              <Typography variant="body2" color="textSecondary">
                                Contributions
                              </Typography>
                            </Box>
                          </Grid>
                        </Grid>
                        
                        <Box sx={{ mt: 2, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <Chip
                            label={`Language: ${repo.primary_language || 'N/A'}`}
                            color="secondary"
                            size="small"
                            sx={{ mr: 1 }}
                          />
                          <Typography variant="body2" color="textSecondary">
                            Last updated: {repo.last_updated || 'N/A'}
                          </Typography>
                        </Box>
                      </CardContent>
                    </Card>
                  </Grid>
                ))}
            </Grid>
          </Grid>
        ) : (
          <Grid item xs={12}>
            <Card sx={{ borderRadius: 3, p: 3, mt: 4 }}>
              <Box sx={{ textAlign: 'center', py: 3 }}>
                <GitHub sx={{ fontSize: 60, color: 'text.secondary', opacity: 0.5, mb: 2 }} />
                <Typography variant="h6" color="textSecondary">
                  No repository contributions data available
                </Typography>
                <Typography variant="body2" color="textSecondary" sx={{ mt: 1 }}>
                  This developer hasn't made contributions to any repositories that we could analyze.
                </Typography>
              </Box>
            </Card>
          </Grid>
        )}
        
        {/* Action Buttons */}
        <Grid item xs={12}>
          <Box sx={{ mt: 4, display: 'flex', justifyContent: 'center', gap: 2 }}>
            <Button 
              variant="contained" 
              color="primary" 
              startIcon={<Download />}
              sx={{ borderRadius: 2, px: 3 }}
            >
              Download Report
            </Button>
            <Button 
              variant="outlined" 
              color="primary" 
              startIcon={<Share />}
              sx={{ borderRadius: 2, px: 3 }}
            >
              Share Profile
            </Button>
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnalysisResults; 