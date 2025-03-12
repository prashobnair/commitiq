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
} from '@mui/material';
import {
  Code,
  MergeType,
  BugReport,
  RateReview,
  Commit,
  TrendingUp,
} from '@mui/icons-material';
import { AnalysisResponse, MetricCard } from '../../types/analysis';

interface Props {
  data: AnalysisResponse;
}

const AnalysisResults: React.FC<Props> = ({ data }) => {
  const theme = useTheme();

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

  const metrics: MetricCard[] = [
    {
      title: 'Merged PRs',
      value: data.analysis.merged_prs || 0,
      description: 'Successfully merged pull requests',
      icon: MergeType,
      color: theme.palette.success.main,
    },
    {
      title: 'Issues Created',
      value: data.analysis.issues_created || 0,
      description: 'Issues opened and tracked',
      icon: BugReport,
      color: theme.palette.info.main,
    },
    {
      title: 'Code Reviews',
      value: data.analysis.code_reviews || 0,
      description: 'Pull request reviews conducted',
      icon: RateReview,
      color: theme.palette.secondary.main,
    },
    {
      title: 'Total Commits',
      value: data.analysis.total_commits || 0,
      description: 'Code contributions made',
      icon: Commit,
      color: theme.palette.primary.main,
    },
    {
      title: 'Project Impact',
      value: (data.analysis.project_impact || 0).toFixed(1),
      description: 'Overall project influence score',
      icon: TrendingUp,
      color: theme.palette.warning.main,
    },
  ];

  return (
    <Box sx={{ py: 4 }}>
      <Grid container spacing={3}>
        {/* Impact Score */}
        <Grid item xs={12}>
          <Card
            sx={{
              background: `linear-gradient(45deg, ${theme.palette.primary.main} 30%, ${theme.palette.secondary.main} 90%)`,
              color: 'white',
              position: 'relative',
              overflow: 'hidden',
            }}
          >
            <CardContent sx={{ position: 'relative', zIndex: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Box>
                  <Typography variant="h6" gutterBottom>
                    Impact Score
                  </Typography>
                  <Typography variant="h2" component="div" sx={{ mb: 1 }}>
                    {(data.impact_score || 0).toFixed(1)}
                  </Typography>
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
                    }}
                  />
                </Box>
                <Code sx={{ fontSize: 80, opacity: 0.2 }} />
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Metrics */}
        {metrics.map((metric, index) => (
          <Grid item xs={12} sm={6} md={4} key={index}>
            <Card>
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
                      bgcolor: `${metric.color}15`,
                      color: metric.color,
                      mr: 2,
                    }}
                  >
                    <metric.icon />
                  </Avatar>
                  <Box>
                    <Typography color="textSecondary" variant="overline">
                      {metric.title}
                    </Typography>
                    <Typography variant="h4">{metric.value}</Typography>
                  </Box>
                </Box>
                <Typography color="textSecondary" variant="body2">
                  {metric.description}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}

        {/* Repositories */}
        <Grid item xs={12}>
          <Typography variant="h5" gutterBottom sx={{ mt: 2 }}>
            Repository Contributions
          </Typography>
          <Grid container spacing={2}>
            {(data.analysis.repos || []).map((repo, index) => (
              <Grid item xs={12} md={6} key={index}>
                <Card>
                  <CardContent>
                    <Typography variant="h6" gutterBottom>
                      <Link
                        href={repo.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        sx={{ textDecoration: 'none' }}
                      >
                        {repo.name}
                      </Link>
                    </Typography>
                    <Grid container spacing={2}>
                      <Grid item xs={6}>
                        <Typography color="textSecondary" variant="body2">
                          Stars
                        </Typography>
                        <Typography variant="body1">{repo.stars || 0}</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography color="textSecondary" variant="body2">
                          Forks
                        </Typography>
                        <Typography variant="body1">{repo.forks || 0}</Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography color="textSecondary" variant="body2">
                          Contributors
                        </Typography>
                        <Typography variant="body1">
                          {repo.num_contributors || 0}
                        </Typography>
                      </Grid>
                      <Grid item xs={6}>
                        <Typography color="textSecondary" variant="body2">
                          Commits
                        </Typography>
                        <Typography variant="body1">{repo.num_commits || 0}</Typography>
                      </Grid>
                    </Grid>
                    <Box sx={{ mt: 2 }}>
                      <Chip
                        label={`Impact: ${(repo.impact_score || 0).toFixed(1)}`}
                        color="primary"
                        size="small"
                        sx={{ mr: 1 }}
                      />
                      <Chip
                        label={`Frequency: ${repo.commit_frequency || 'N/A'}`}
                        color="secondary"
                        size="small"
                      />
                    </Box>
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </Grid>
      </Grid>
    </Box>
  );
};

export default AnalysisResults; 