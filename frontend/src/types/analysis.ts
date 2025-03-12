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