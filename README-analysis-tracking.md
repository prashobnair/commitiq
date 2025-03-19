# GitHub Analysis Tracking System

This document outlines the implementation of the GitHub Analysis Tracking System for CommitIQ, which captures data about GitHub profiles analyzed by users of the platform.

## Overview

The GitHub Analysis Tracking System records detailed information about each GitHub profile analysis performed through CommitIQ. It stores both the raw analysis results and structured metrics, allowing for insights into:

1. Which GitHub profiles are being analyzed
2. What the analysis results are showing
3. Which users are analyzing which profiles
4. Patterns in GitHub profile metrics and impact scores

## Database Schema

### Main Tables

#### 1. `github_analysis`

Stores the core information about each analysis:

- **id**: Primary key
- **github_username**: The GitHub username that was analyzed
- **analyzer_email**: Email of the user who performed the analysis (if known)
- **impact_score**: The calculated impact score for the profile
- **developer_summary**: Text summary of the developer's profile
- **analyzed_at**: Timestamp when the analysis was performed
- **analyzed_from_ip**: IP address of the user (hashed for privacy)
- **user_agent**: Browser/client information
- **is_successful**: Boolean indicating if the analysis was successful
- **error_message**: Error message if the analysis failed

#### 2. `github_analysis_details`

Stores detailed metrics for each analysis:

- **id**: Primary key
- **analysis_id**: Foreign key to github_analysis
- **total_commits**: Number of commits
- **pull_requests**: Number of pull requests
- **issues_raised**: Number of issues opened
- **code_reviews**: Number of code reviews performed
- **consistency_score**: Score representing contribution consistency
- **project_impact_score**: Score representing impact on projects
- **strengths**: JSONB array of developer strengths
- **considerations**: JSONB array of developer considerations/weaknesses
- **top_languages**: JSONB object of language usage statistics
- **top_repositories**: JSONB array of top repository data
- **full_analysis_data**: Complete JSON of the analysis result
- **created_at**: Timestamp

### Indexes

- Index on `github_username` for quick lookups by username
- Foreign key constraints to ensure data integrity

## API Endpoints

### Analysis Tracking

- **POST /api/analyze/{username}**: Perform an analysis (updated to store tracking data)
- **GET /api/tracking/recent**: Get recent analyses (admin only)

### Dashboard

- **GET /api/dashboard/**: Main dashboard view with summary statistics
- **GET /api/dashboard/analysis/{id}**: Detailed view of a specific analysis
- **GET /api/dashboard/stats**: Statistical analysis of GitHub profiles

## Integration Points

### 1. Analysis API Integration

The `analyze_user` endpoint has been updated to:
- Record successful analyses with all metrics
- Track failed analyses with error information
- Capture information about the user performing the analysis

### 2. Waitlist Integration

Waitlist user information is linked to analysis data through:
- The `analyzer_email` field in the github_analysis table
- Utility functions that can connect anonymous analyses to known waitlist users

## Security Considerations

- User IP addresses are hashed for privacy
- Access to tracking data is restricted to admin routes
- Personal information is stored according to privacy policy requirements

## Utility Functions

The implementation includes several utility functions to facilitate data access:

- `store_analysis_result()`: Store an analysis result in the database
- `link_waitlist_user_to_analysis()`: Connect a waitlist user to their analysis activities
- `get_user_analysis_history()`: Retrieve a user's analysis history
- `get_top_analyzed_profiles()`: Identify the most frequently analyzed GitHub profiles
- `get_waitlist_user_engagement_metrics()`: Calculate user engagement metrics

## Dashboard Features

The tracking dashboard provides:

1. Summary statistics on analyses performed
2. Most frequently analyzed profiles
3. Average impact scores and metrics
4. Analysis success/failure rates
5. User engagement metrics

## Installation and Setup

1. The tables are automatically created when the application starts
2. No additional configuration is required beyond database connection settings

## Usage Examples

### Storing Analysis Results

```python
from app.api.analysis_tracking import store_analysis_result

# Store a successful analysis
store_analysis_result(
    github_username="octocat",
    analysis_result=result_data,
    analyzer_email="recruiter@company.com",
    request_info={
        'ip': request.remote_addr,
        'user_agent': request.headers.get('User-Agent')
    }
)
```

### Accessing Analysis Data

```python
from app.utils.user_tracking import get_user_analysis_history

# Get a user's analysis history
analyses = get_user_analysis_history(email="recruiter@company.com")
```

## Future Enhancements

Potential future enhancements include:

1. More sophisticated analytics on profile patterns
2. Machine learning to identify high-potential developers based on metrics
3. Automated reporting and alerting
4. Deeper integration with user accounts and permissions
5. Enhanced visualization of analysis trends 