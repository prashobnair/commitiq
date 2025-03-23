import React, { useState } from 'react';
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
  Accordion,
  AccordionSummary,
  AccordionDetails,
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
  ArrowBack,
  ExpandMore,
  Home as HomeIcon,
} from '@mui/icons-material';
import { AnalysisResponse, MetricCard, Repository, Contributions } from '../../types/analysis';
import ShareOptions from './ShareOptions';
import { useAnalysisContext } from '../../contexts/AnalysisContext';
import { Link as RouterLink } from 'react-router-dom';

interface Props {
  data: AnalysisResponse;
  onJoinWaitingList?: () => void;
  isSharedView?: boolean;
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
  // Check if impact score is 0 - special case
  if (data.impact_score === 0) {
    const developerName = data.analysis.name || data.analysis.username;
    return `${developerName} has no measurable GitHub activity in our analysis period. This could mean they're new to GitHub, work primarily in private repositories, or contribute through other means not captured in our analysis.`;
  }
  
  // Extract contribution data from the correct location in the response
  const contributions = data.analysis.contributions || emptyContributions;
  const pulls = contributions.pulls;
  const commits = contributions.commits;
  const consistency = contributions.consistency;
  const reviews = contributions.reviews;
  const repos_impact = contributions.repos_impact;
  
  // Get developer name or username
  const developerName = data.analysis.name || data.analysis.username;
  
  // Determine primary language focus if available
  let languageFocus = "";
  if (contributions.top_languages && contributions.top_languages.length > 0) {
    const topLang = contributions.top_languages[0];
    const langName = typeof topLang === 'object' && topLang !== null ? topLang.language : '';
    if (langName) {
      languageFocus = ` with particular focus on ${langName} development`;
    }
  }
  
  // Create a list of key insights, prioritized by importance
  const insights: string[] = [];
  
  // Collaboration style (highest priority)
  if (pulls > 30 && reviews > 20) {
    insights.push(`${developerName} demonstrates a highly collaborative approach, actively contributing to team projects and providing thoughtful feedback${languageFocus}`);
  } else if (pulls > 15 && reviews > 10) {
    insights.push(`${developerName} shows good team collaboration skills, regularly contributing to shared codebases${languageFocus}`);
  } else if (commits > 100 && (pulls < 10 || reviews < 5)) {
    insights.push(`${developerName} tends to focus on independent development, with strong contribution volume but less emphasis on collaborative workflows${languageFocus}`);
  } else {
    insights.push(`${developerName} balances independent work with team collaboration${languageFocus}`);
  }
  
  // Consistency and reliability (medium priority)
  if (consistency > 0.8) {
    insights.push("Their highly consistent activity pattern indicates strong reliability and sustained engagement over time");
  } else if (consistency > 0.6) {
    insights.push("They maintain good consistency in their development work, suggesting reliable engagement");
  } else if (consistency > 0.4) {
    insights.push("Their moderate consistency suggests periodic focused engagement rather than continuous development");
  } else if (commits > 50) {
    insights.push("Their engagement pattern shows variability, potentially indicating project-based work rather than ongoing maintenance");
  }
  
  // Code quality focus (medium priority)
  if (reviews > commits * 0.3) {
    insights.push("Their significant focus on code reviews demonstrates a commitment to code quality and mentorship");
  } else if (reviews > commits * 0.1) {
    insights.push("They regularly participate in code reviews, showing attention to quality and collaborative improvement");
  } else if (reviews > 10) {
    insights.push("They occasionally engage in code review processes, providing some quality oversight");
  }
  
  // Project impact (lower priority)
  if (repos_impact > 0.05) {
    insights.push("Their contributions demonstrate significant impact across repositories, suggesting influence on important projects");
  } else if (repos_impact > 0.02 && commits > 50) {
    insights.push("They show meaningful impact on the repositories they contribute to");
  }
  
  // Limit to the most important 3 insights (at most 4 if they're short)
  let summaryText = "";
  const maxSentences = 4;
  let sentenceCount = 0;
  
  for (let i = 0; i < insights.length && sentenceCount < maxSentences; i++) {
    if (summaryText) summaryText += " ";
    summaryText += insights[i] + ".";
    sentenceCount++;
  }
  
  return summaryText;
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
const getStrengthsAndConsiderations = (data: AnalysisResponse): { strengths: string[]; considerations: string[] } => {
  // Extract contribution data from the correct location in the response
  const contributions = data.analysis.contributions || emptyContributions;
  const pulls = contributions.pulls;
  const commits = contributions.commits;
  const consistency = contributions.consistency;
  const reviews = contributions.reviews;
  const repos_impact = contributions.repos_impact;
  const topLanguages = contributions.top_languages || [];
  const topRepos = contributions.top_repositories || [];
  
  const allStrengths: string[] = [];
  const allConsiderations: string[] = [];
  
  // Analyze collaboration patterns
  if (pulls > 30 && commits > 100) {
    allStrengths.push('Strong balance of code contribution and collaborative development through pull requests');
  } else if (pulls > 20) {
    allStrengths.push('Demonstrates effective collaborative workflow through regular pull request contributions');
  } else if (commits > 200 && pulls > 10) {
    allStrengths.push('High volume of code contributions with moderate collaborative engagement');
  }
  
  // Analyze consistency patterns
  if (consistency > 0.8) {
    allStrengths.push('Exceptional consistency in development activity, suggesting strong reliability and sustained engagement');
  } else if (consistency > 0.6) {
    allStrengths.push('Maintains good consistency in development work, indicating reliable contribution patterns');
  } else if (consistency < 0.4 && commits > 100) {
    allConsiderations.push('Contributions tend to be concentrated in intense periods rather than consistent engagement');
  }
  
  // Analyze code quality focus
  if (reviews > 30) {
    allStrengths.push('Strong commitment to code quality through frequent and detailed code reviews');
  } else if (reviews > 15) {
    allStrengths.push('Regular participation in code review processes, demonstrating attention to quality');
  } else if (commits > 100 && reviews < 5) {
    allConsiderations.push('Limited engagement in code review processes compared to contribution volume');
  }
  
  // Analyze specialization and focus areas
  if (topLanguages && topLanguages.length > 0) {
    const topLang = topLanguages[0];
    const langName = typeof topLang === 'object' && topLang !== null ? topLang.language : '';
    if (langName) {
      allStrengths.push(`Demonstrates strong specialization in ${langName} development`);
    }
    
    // Check for language diversity
    if (topLanguages.length >= 3) {
      allStrengths.push('Versatile across multiple programming languages, suggesting adaptability to different technical requirements');
    }
  } else {
    allConsiderations.push('Limited data on language specialization, making it difficult to assess technical focus areas');
  }
  
  // Analyze project impact
  if (repos_impact > 0.05) {
    allStrengths.push('Significant impact on project repositories, suggesting meaningful contributions to important codebases');
  } else if (repos_impact < 0.02 && commits > 100) {
    allConsiderations.push('Contributions may be spread across many repositories or focused on less central codebases');
  }
  
  // Analyze repository contribution patterns
  if (topRepos && topRepos.length > 0) {
    const hasHighStarRepo = topRepos.some(repo => repo.stars > 100);
    if (hasHighStarRepo) {
      allStrengths.push('Experience contributing to popular, widely-used repositories');
    }
    
    const hasHighImpactContributions = topRepos.some(repo => {
      const impactScore = repo.impact_score || 0;
      let contributionRatio = 0;
      
      // Try to parse contribution ratio from various possible formats
      if (typeof repo.num_commits === 'string') {
        const match = repo.num_commits.match(/(\d+(\.\d+)?)%/);
        if (match) {
          contributionRatio = parseFloat(match[1]);
        }
      }
      
      return impactScore > 0.05 || contributionRatio > 10;
    });
    
    if (hasHighImpactContributions) {
      allStrengths.push('Demonstrated ability to make significant contributions to individual projects');
    }
  }
  
  // Ensure we have at least one strength
  if (allStrengths.length === 0) {
    if (commits > 0 || pulls > 0) {
      allStrengths.push('Shows engagement with GitHub projects, demonstrating basic version control competence');
    } else {
      allStrengths.push('Has established a GitHub presence, though activity metrics are limited');
    }
  }
  
  // If no considerations, add an appropriate one
  if (allConsiderations.length === 0) {
    if (consistency < 0.7 && consistency > 0.4) {
      allConsiderations.push('Moderate consistency in development activity may indicate varying engagement levels over time');
    } else if (pulls < 20 && reviews < 15 && pulls > 0) {
      allConsiderations.push('Could benefit from increased engagement with collaborative development workflows');
    } else if (commits < 50 && pulls < 10) {
      allConsiderations.push('Limited volume of public GitHub activity, which may not fully represent technical capabilities');
    } else {
      allConsiderations.push('No significant concerns identified in the contribution pattern');
    }
  }
  
  // Prioritize and limit strengths and considerations to 3 each
  const strengths = allStrengths.slice(0, 3);
  const considerations = allConsiderations.slice(0, 3);
  
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
    
    // Use the URL if it exists, otherwise construct one from the name
    let repoUrl = repo.url || '#';
    if (!repoUrl && repo.name) {
      repoUrl = `https://github.com/${repo.name}`;
    }
    
    // Format last_commit_date if it exists
    let lastUpdated = 'N/A';
    if (repo.last_commit_date && repo.last_commit_date !== 'N/A') {
      lastUpdated = formatDate(repo.last_commit_date);
    }
    
    // Parse contribution ratio from various possible formats
    let contributionRatio = '0%';
    if (repo.contribution_ratio) {
      contributionRatio = `${(repo.contribution_ratio * 100).toFixed(1)}%`;
    } else if (typeof repo.contributionRatio === 'number') {
      contributionRatio = `${repo.contributionRatio}%`;
    } else if (typeof repo.contributionRatio === 'string') {
      contributionRatio = repo.contributionRatio;
    }
    
    // Map the repository data to our component format
    return {
      name: repo.name || 'Unknown Repository',
      url: repoUrl,
      stars: repo.stars || 0,
      forks: repo.forks || 0,
      num_contributors: repo.collaborators || repo.num_contributors || 0,
      primary_language: repo.primaryLanguage || repo.primary_language || 'N/A',
      commit_frequency: repo.commit_frequency || 'N/A',
      last_updated: lastUpdated,
      num_commits: contributionRatio,
      impact_score: repo.impact_score || repo.impactScore || repo.repo_impact || 0
    };
  });
};

const AnalysisResults: React.FC<Props> = ({ data, onJoinWaitingList, isSharedView = false }) => {
  const theme = useTheme();
  const { resetAnalysis } = useAnalysisContext();
  // Single state to track expanded accordion
  const [expandedAdvancedMetrics, setExpandedAdvancedMetrics] = useState<boolean>(false);
  
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
    console.log("Raw top_languages data:", contributions.top_languages);
    
    // Map the languages to a consistent format
    topLanguages = contributions.top_languages.map((lang: any) => {
      // Check if the language data is in the expected format
      if (typeof lang === 'object' && lang !== null) {
        // Use name as the primary field, fallback to language if name is not available
        const languageName = lang.name || lang.language || 'Unknown';
        
        // Check if percentage is already in percentage format (> 1) or decimal format (< 1)
        let percentage = 0;
        if (typeof lang.percentage === 'number') {
          // For anshphirani's case, the percentages are already correct (99 and 1)
          // So we should not modify them if they sum close to 100
          percentage = lang.percentage;
        } else if (typeof lang.percent === 'number') {
          percentage = lang.percent;
        }
        
        console.log(`Processing language ${languageName}: raw percentage = ${percentage}`);
        
        return {
          language: languageName,
          percentage: percentage
        };
      }
      // Default case for any other format
      return { language: 'Unknown', percentage: 0 };
    });

    // Log the final processed languages
    console.log("Final processed languages:", topLanguages);
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
            percentage = lang.percentage;
          } else if (typeof lang.percent === 'number') {
            percentage = lang.percent;
          }
          
          console.log(`Processing language from metrics ${languageName}: raw percentage = ${percentage}`);
          
          return {
            language: languageName,
            percentage: percentage
          };
        });
        
        console.log("Final processed languages from metrics:", topLanguages);
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

  // Extract analysis ID for share/download functionality
  const analysisId = (data as any).id || 0;
  const githubUsername = (data as any).github_username || data.analysis.username || '';

  return (
    <Box sx={{ py: 4 }}>
      <Grid container spacing={3} display="flex" flexDirection={{ xs: 'column', md: 'row' }}>
        {/* Back Button */}
        <Grid item xs={12}>
          {isSharedView ? (
            <Button
              variant="outlined"
              color="primary"
              startIcon={<HomeIcon />}
              sx={{ mb: 3 }}
              onClick={() => window.location.href = '/'}
            >
              Return to Home
            </Button>
          ) : (
            <Button
              variant="outlined"
              color="primary"
              onClick={resetAnalysis}
              startIcon={<ArrowBack />}
              sx={{ mb: 3 }}
            >
              Back to Search
            </Button>
          )}
        </Grid>
        
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

        {/* Main content row with equal height columns */}
        <Grid item xs={12}>
          <Box sx={{ 
            display: 'flex', 
            flexDirection: { xs: 'column', md: 'row' },
            gap: 3,
            mb: 3
          }}>
            {/* Left Column - Impact Score and Top Languages */}
            <Box sx={{ 
              flex: 1,
              display: 'flex',
              flexDirection: 'column',
              gap: 3
            }}>
              {/* Impact Score */}
              <Card sx={{ 
                borderRadius: 3,
                background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
                color: 'white',
                flex: topLanguages && topLanguages.length > 0 ? 7 : 1
              }}>
                <CardContent sx={{ p: 3 }}>
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
                </CardContent>
              </Card>
              
              {/* Top Languages */}
              {topLanguages && topLanguages.length > 0 && (
                <Card sx={{ 
                  borderRadius: 3,
                  flex: 3
                }}>
                  <CardContent sx={{ p: 3 }}>
                    <Typography variant="h6" fontWeight="bold" gutterBottom>
                      Top Languages
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {topLanguages.map((lang, index) => {
                        console.log(`Rendering language ${lang.language} with percentage ${lang.percentage}`);
                        return (
                          <Chip
                            key={index}
                            label={`${lang.language}: ${lang.percentage.toFixed(1)}%`}
                            size="small"
                            sx={{
                              bgcolor: `${theme.palette.primary.main}15`,
                              color: theme.palette.primary.main,
                              my: 0.5
                            }}
                          />
                        );
                      })}
                    </Box>
                  </CardContent>
                </Card>
              )}
            </Box>

            {/* Right Column - Developer Summary */}
            <Box sx={{ flex: 1 }}>
              <Card sx={{ 
                height: '100%', 
                borderRadius: 3
              }}>
                <CardContent sx={{ p: 3 }}>
                  <Typography variant="h6" fontWeight="bold" gutterBottom>
                    Developer Summary
                  </Typography>
                  <Typography variant="body1" sx={{ mb: 2 }}>
                    {summary}
                  </Typography>
                  
                  <Grid container spacing={2}>
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                        Strengths
                      </Typography>
                      {strengths.map((strength, index) => (
                        <Box key={index} sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              bgcolor: 'success.main',
                              mr: 1.5,
                              mt: 0.7,
                              flexShrink: 0
                            }}
                          />
                          <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                            {strength}
                          </Typography>
                        </Box>
                      ))}
                    </Grid>
                    
                    <Grid item xs={12} md={6}>
                      <Typography variant="subtitle1" fontWeight="bold" gutterBottom>
                        Considerations
                      </Typography>
                      {considerations.map((consideration, index) => (
                        <Box key={index} sx={{ display: 'flex', alignItems: 'flex-start', mb: 1 }}>
                          <Box
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: '50%',
                              bgcolor: 'warning.main',
                              mr: 1.5,
                              mt: 0.7,
                              flexShrink: 0
                            }}
                          />
                          <Typography variant="body2" sx={{ wordBreak: 'break-word' }}>
                            {consideration}
                          </Typography>
                        </Box>
                      ))}
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            </Box>
          </Box>
        </Grid>

        {/* Deep Insights Accordion */}
        <Grid item xs={12}>
          <Accordion 
            expanded={expandedAdvancedMetrics} 
            onChange={() => setExpandedAdvancedMetrics(!expandedAdvancedMetrics)}
            sx={{ mt: 4, mb: 3, borderRadius: 2, overflow: 'hidden' }}
          >
            <AccordionSummary
              expandIcon={<ExpandMore />}
              aria-controls="deep-insights-content"
              id="deep-insights-header"
              sx={{ 
                background: `linear-gradient(90deg, ${theme.palette.primary.main}10, ${theme.palette.secondary.main}10)`,
                borderRadius: 1
              }}
            >
              <Typography variant="subtitle1" fontWeight="medium" color="text.primary" sx={{ display: 'flex', alignItems: 'center' }}>
                <BarChart sx={{ mr: 1, color: theme.palette.primary.main }} />
                {expandedAdvancedMetrics ? 'Hide Deep Insights' : 'Show Deep Insights'}
              </Typography>
            </AccordionSummary>
            <AccordionDetails sx={{ p: 3 }}>
              {/* Detailed Key Metrics Section */}
              <Typography variant="h6" fontWeight="bold" gutterBottom sx={{ mb: 3 }}>
                Key Metrics
              </Typography>
              <Grid container spacing={3} sx={{ mb: 4 }}>
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

              {/* Repository Details Section */}
              {repositories && repositories.length > 0 ? (
                <>
                  <Divider sx={{ my: 4 }} />
                  <Typography variant="h6" fontWeight="bold" gutterBottom sx={{ mb: 3 }}>
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
                </>
              ) : (
                <>
                  <Divider sx={{ my: 4 }} />
                  <Card sx={{ borderRadius: 3, p: 3 }}>
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
                </>
              )}
            </AccordionDetails>
          </Accordion>
        </Grid>
        
        {/* Replace the Action Buttons with ShareOptions component */}
        <Grid item xs={12}>
          <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <ShareOptions 
              analysisId={analysisId} 
              githubUsername={githubUsername} 
            />
            
            {onJoinWaitingList && (
              <Button 
                variant="contained" 
                color="secondary" 
                onClick={onJoinWaitingList}
                sx={{ borderRadius: 2, px: 3, fontWeight: 600, mt: 2 }}
              >
                Join Waiting List
              </Button>
            )}
          </Box>
        </Grid>
      </Grid>
    </Box>
  );
};
export default AnalysisResults; 
