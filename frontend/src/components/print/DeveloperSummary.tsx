import React from 'react';
import { Box, Typography } from '@mui/material';

interface DeveloperSummaryProps {
  username: string;
  name?: string;
  commits: number;
  pulls: number;
  consistency: number;
  reviews: number;
}

/**
 * Developer Summary component for the print/PDF view
 */
const DeveloperSummary: React.FC<DeveloperSummaryProps> = ({ 
  username, 
  name, 
  commits, 
  pulls, 
  consistency, 
  reviews 
}) => {
  // Helper function to determine rating based on value
  const getRating = (value: number, type: 'prs' | 'commits' | 'consistency'): string => {
    if (type === 'prs') {
      if (value > 50) return 'high';
      if (value > 20) return 'above average';
      if (value > 10) return 'moderate';
      return 'low';
    } else if (type === 'commits') {
      if (value > 300) return 'high';
      if (value > 100) return 'above average';
      if (value > 50) return 'moderate';
      return 'low';
    } else if (type === 'consistency') {
      if (value > 0.8) return 'excellent';
      if (value > 0.6) return 'good';
      if (value > 0.4) return 'moderate';
      return 'inconsistent';
    }
    return 'moderate';
  };

  const developerName = name || username;
  
  // Check if this is a zero-activity profile
  if (commits === 0 && pulls === 0 && reviews === 0) {
    // Special case for users with no activity
    const summary = `${developerName} has no measurable GitHub activity in our analysis period. This could mean they're new to GitHub, work primarily in private repositories, or contribute through other means not captured in our analysis.`;
    
    return (
      <Box sx={{ mb: 4 }}>
        <Typography variant="h6" gutterBottom>
          Developer Summary
        </Typography>
        
        <Typography variant="body1">
          {summary}
        </Typography>
      </Box>
    );
  }

  // For normal users with activity
  const prRating = getRating(pulls, 'prs');
  const commitRating = getRating(commits, 'commits');
  const consistencyRating = getRating(consistency, 'consistency');
  const consistencyPercent = consistency * 100;
  
  // Generate summary text
  const summary = `${developerName} has made ${commits} commits and ${pulls} pull requests, showing ${prRating} collaboration. Their consistency is ${consistencyPercent.toFixed(1)}%, indicating ${consistencyRating} regular activity. With ${reviews} code reviews, they actively engage in code discussions. Overall, they're a ${commitRating} contributor who ${pulls > 30 ? 'frequently' : 'occasionally'} participates in various projects.`;

  return (
    <Box sx={{ mb: 4 }}>
      <Typography variant="h6" gutterBottom>
        Developer Summary
      </Typography>
      
      <Typography variant="body1">
        {summary}
      </Typography>
    </Box>
  );
};

export default DeveloperSummary; 