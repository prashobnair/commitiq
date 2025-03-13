import { ElementType } from 'react';

export interface Repository {
  name: string;
  url: string;
  stars: number;
  forks: number;
  num_contributors: number;
  commit_frequency: string;
  last_updated: string;
  num_commits: number;
  impact_score: number;
}

export interface Contributions {
  commits: number;
  consistency: number;
  issues: number;
  pulls: number;
  repos_impact: number;
  reviews: number;
}

export interface Metrics {
  consistency?: {
    active_days: number;
    active_days_ratio: number;
    active_weeks: number;
    avg_contributions_per_active_day: number;
    total_contributions: number;
    total_days: number;
    total_weeks: number;
  };
  repos_impact?: {
    average_impact: number;
    impact_weights: {
      ecosystem: number;
      technical: number;
    };
    max_impact: number;
    median_impact: number;
    min_impact: number;
    repo_count: number;
  };
  repositories?: any[]; // Array of repository metrics
}

export interface Analysis {
  username: string;
  merged_prs: number;
  issues_created: number;
  issues_resolved: number;
  code_reviews: number;
  total_commits: number;
  project_impact: number;
  consistency: number;
  repos: Repository[];
  contributions?: Contributions;
  metrics?: Metrics;
  bio?: string | null;
  company?: string | null;
  email?: string;
  followers?: number;
  following?: number;
  has_activity?: boolean;
  location?: string;
  name?: string;
  url?: string | null;
  avatar_url?: string;
}

export interface AnalysisResponse {
  analysis: Analysis;
  impact_score: number;
}

export interface MetricCard {
  title: string;
  value: number | string;
  description: string;
  icon: ElementType;
  color?: string;
} 