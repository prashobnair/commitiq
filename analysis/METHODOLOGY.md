# Methodology for Impact Score Threshold Validation

This document explains the methodology used to validate and optimize the thresholds, constants, and weights used in the CommiTiq impact score calculation algorithm.

## Overview

The CommiTiq impact score is calculated using a combination of metrics derived from a developer's GitHub activity, with each metric contributing differently to the final score. The calculation involves normalization thresholds, weighting factors, and various constants that affect how different metrics are interpreted.

Our validation approach uses real GitHub user data to empirically determine optimal values for these parameters, ensuring that the impact score accurately reflects a developer's contributions and impact.

## Data Sources

The analysis uses the following data tables from the PostgreSQL database:

- `users_github`: Basic information about GitHub users
- `users_metrics`: Metrics and impact scores for each user
- `users_repositories`: Repository information for each user
- `users_repositories_metrics`: Detailed metrics for each repository

## Validation Methodology

### 1. Normalization Thresholds

Normalization thresholds are used to convert raw metrics (e.g., number of commits) into a 0-100 percentile score. The current implementation uses fixed min/max thresholds for each metric:

```python
NORMALIZATION_THRESHOLDS = {
    'pulls': (5, 100),
    'commits': (10, 250),
    'reviews': (5, 100),
    'issues': (2, 50),
    'repos_impact': (10, 100),
    'consistency': (10, 35)
}
```

Our validation:
1. Analyzes the distribution of each metric across all users
2. Calculates key percentiles (10th, 50th, 90th, 95th, 99th)
3. Recommends:
   - The 10th percentile as the minimum threshold (ensuring most users have a non-zero score)
   - The 95th percentile as the maximum threshold (avoiding extreme outliers)

### 2. Impact Score Weights

The impact score is calculated as a weighted sum of normalized metrics, with the current weights:

```python
IMPACT_SCORE_WEIGHTS = {
    'pulls': 0.27,
    'commits': 0.225,
    'reviews': 0.135,
    'issues': 0.09,
    'repos_impact': 0.18,
    'consistency': 0.10
}
```

Our validation:
1. Uses regression analysis to determine the relationship between individual metrics and the final impact score
2. Applies two approaches:
   - Linear Regression: Direct mapping of coefficients 
   - Random Forest: Feature importance analysis
3. Combines these approaches to recommend optimal weights that:
   - Reflect the true importance of each metric
   - Sum to 1.0 to maintain the 0-100 scale

### 3. Repository Impact Weights

Repository impact combines technical impact and ecosystem impact with current weights:

```python
REPO_IMPACT_WEIGHTS = {
    'technical': 0.7,
    'ecosystem': 0.3
}
```

Our validation:
1. Analyzes the correlation between technical/ecosystem impact and overall repo impact
2. Uses Ordinary Least Squares (OLS) regression to find optimal coefficients
3. Normalizes coefficients to recommend weights that sum to 1.0

### 4. Contribution Ratio Exponent

The contribution ratio exponent (currently 0.7) applies diminishing returns for higher contribution percentages:

```python
contribution_ratio ** CONTRIBUTION_RATIO_EXPONENT
```

Our validation:
1. Tests different exponent values (0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
2. Fits regression models for each exponent
3. Selects the exponent with the highest R² value (best fit)

### 5. Collaboration Factor Parameters

Collaboration factor is calculated using several parameters:

```python
min(COLLAB_FACTOR['base'] + math.log(collaborators + 1) * COLLAB_FACTOR['log_factor'], 
    COLLAB_FACTOR['max_value'])
```

Our validation:
1. Performs a grid search across parameter combinations:
   - Base values: [0.8, 1.0, 1.2]
   - Log factors: [0.3, 0.4, 0.5, 0.6]
   - Max values: [2.0, 2.5, 3.0]
2. For each combination, calculates the correlation with repo impact
3. Selects the parameter combination that maximizes correlation

### 6. Review Activity Normalization

Review activity is normalized using a factor (currently 100.0):

```python
min(review_comments / REVIEW_ACTIVITY['normalization_factor'], 1.0)
```

Our validation:
1. Analyzes the distribution of review comments across all repositories
2. Recommends the 75th percentile as the normalization factor (balancing between common cases and preventing too many values from being capped at 1.0)

## Statistical Techniques

The validation employs several statistical techniques:

1. **Descriptive Statistics**: Percentiles, mean, median to understand metric distributions
2. **Linear Regression**: Finding optimal coefficients for weighting factors
3. **Random Forest**: Alternative approach for determining feature importance
4. **Correlation Analysis**: Measuring relationships between metrics
5. **Grid Search**: Systematically testing parameter combinations
6. **R² Analysis**: Measuring goodness of fit for regression models

## Implementation

The validation is implemented using Python with the following key libraries:
- `pandas` for data manipulation
- `numpy` for numerical operations
- `scikit-learn` for machine learning models
- `statsmodels` for statistical analysis
- `matplotlib` and `seaborn` for visualization

## Limitations and Considerations

1. **Data Quality**: The analysis assumes the existing data accurately represents GitHub activity.
2. **Overfitting**: Recommendations are based on the current dataset and might need periodic updates as more user data is collected.
3. **Ground Truth**: There's no objective "true" impact score to validate against; we're optimizing relative to the current algorithm's output.
4. **Subjective Elements**: Some aspects of developer impact remain subjective and can't be fully captured by statistical analysis.

## Recommendations for Future Work

1. **Periodic Revalidation**: As more user data is collected, rerun the analysis to ensure thresholds remain appropriate.
2. **A/B Testing**: Test different sets of parameters with real users to gather feedback.
3. **Additional Metrics**: Consider incorporating additional metrics that might better capture developer impact.
4. **User Segmentation**: Analyze whether different thresholds might be appropriate for different types of developers (e.g., frontend vs. backend). 