"""
Analysis module to validate and optimize impact score thresholds and constants.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from sklearn.preprocessing import MinMaxScaler
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import statsmodels.api as sm
from sklearn.ensemble import RandomForestRegressor
from db_connection import (
    fetch_users_data, fetch_users_metrics, fetch_users_repositories,
    fetch_users_repositories_metrics, fetch_joined_user_data,
    fetch_repository_with_metrics
)

# Current constants from the backend code
CURRENT_THRESHOLDS = {
    'normalization': {
        'pulls': (5, 100),
        'commits': (10, 250),
        'reviews': (5, 100),
        'issues': (2, 50),
        'repos_impact': (10, 100),
        'consistency': (10, 35)
    },
    'repo_impact': {
        'technical': 0.7,
        'ecosystem': 0.3
    },
    'technical_impact': {
        'pr_acceptance': 0.6,
        'review_activity': 0.4
    },
    'impact_score': {
        'pulls': 0.27,
        'commits': 0.225,
        'reviews': 0.135,
        'issues': 0.09,
        'repos_impact': 0.18,
        'consistency': 0.10
    },
    'collab_factor': {
        'base': 1.0,
        'log_factor': 0.5,
        'max_value': 2.5
    },
    'review_activity': {
        'normalization_factor': 100.0
    },
    'contribution_ratio_exponent': 0.7
}

class ThresholdAnalyzer:
    """Class to analyze GitHub user data and validate scoring thresholds and constants."""
    
    def __init__(self, output_dir='../results'):
        """
        Initialize the analyzer.
        
        Args:
            output_dir (str): Directory to save analysis results
        """
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Load data
        self.users = None
        self.metrics = None
        self.repos = None
        self.repo_metrics = None
        self.joined_data = None
        self.joined_repos = None
        
    def load_data(self):
        """Load all necessary data from the database."""
        print("Loading data from database...")
        
        self.users = fetch_users_data()
        self.metrics = fetch_users_metrics()
        self.repos = fetch_users_repositories()
        self.repo_metrics = fetch_users_repositories_metrics()
        self.joined_data = fetch_joined_user_data()
        self.joined_repos = fetch_repository_with_metrics()
        
        print(f"Data loaded successfully. User count: {len(self.users)}")
        
    def analyze_distributions(self):
        """Analyze the distributions of key metrics to validate normalization thresholds."""
        if self.metrics is None:
            self.load_data()
            
        # Metrics to analyze
        metrics = ['pulls', 'commits', 'reviews', 'issues', 'repos_impact', 'consistency']
        
        # Create distribution plots
        plt.figure(figsize=(15, 15))
        
        for i, metric in enumerate(metrics, 1):
            plt.subplot(3, 2, i)
            
            # Get current thresholds
            curr_min, curr_max = CURRENT_THRESHOLDS['normalization'][metric]
            
            # Plot distribution
            sns.histplot(self.metrics[metric], kde=True)
            plt.axvline(curr_min, color='r', linestyle='--', label=f'Current Min: {curr_min}')
            plt.axvline(curr_max, color='g', linestyle='--', label=f'Current Max: {curr_max}')
            
            # Add percentile lines
            p10 = np.percentile(self.metrics[metric], 10)
            p90 = np.percentile(self.metrics[metric], 90)
            p95 = np.percentile(self.metrics[metric], 95)
            p99 = np.percentile(self.metrics[metric], 99)
            
            plt.axvline(p10, color='purple', linestyle=':', label=f'10th percentile: {p10:.1f}')
            plt.axvline(p90, color='orange', linestyle=':', label=f'90th percentile: {p90:.1f}')
            plt.axvline(p95, color='brown', linestyle=':', label=f'95th percentile: {p95:.1f}')
            
            plt.title(f'Distribution of {metric}')
            plt.legend()
            
            # Recommend new thresholds
            recommended_min = max(1, p10) if metric != 'consistency' else p10
            recommended_max = p95
            
            print(f"\nMetric: {metric}")
            print(f"Current thresholds: min={curr_min}, max={curr_max}")
            print(f"Percentiles: 10th={p10:.1f}, 90th={p90:.1f}, 95th={p95:.1f}, 99th={p99:.1f}")
            print(f"Recommended thresholds: min={recommended_min:.1f}, max={recommended_max:.1f}")
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'metric_distributions.png'))
        
        return {metric: (max(1, np.percentile(self.metrics[metric], 10)), 
                         np.percentile(self.metrics[metric], 95)) 
                for metric in metrics}
    
    def analyze_impact_weights(self):
        """Analyze the importance of different metrics in determining impact score."""
        if self.joined_data is None:
            self.load_data()
            
        # Prepare data for regression analysis
        X = self.joined_data[['pulls', 'commits', 'reviews', 
                         'issues', 'repos_impact', 'consistency']]
        y = self.joined_data['impact_score']
        
        # Normalize the data
        scaler = MinMaxScaler()
        X_scaled = scaler.fit_transform(X)
        X_scaled = pd.DataFrame(X_scaled, columns=X.columns)
        
        # Split the data
        X_train, X_test, y_train, y_test = train_test_split(
            X_scaled, y, test_size=0.2, random_state=42
        )
        
        # Train a linear regression model
        model = LinearRegression()
        model.fit(X_train, y_train)
        
        # Get coefficients
        coefficients = pd.Series(model.coef_, index=X.columns)
        
        # Normalize coefficients to sum to 1
        normalized_coefs = coefficients / coefficients.sum()
        
        # Train a random forest for feature importance comparison
        rf = RandomForestRegressor(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)
        rf_importance = pd.Series(rf.feature_importances_, index=X.columns)
        
        # Compare with current weights
        current_weights = pd.Series({
            'pulls': CURRENT_THRESHOLDS['impact_score']['pulls'],
            'commits': CURRENT_THRESHOLDS['impact_score']['commits'],
            'reviews': CURRENT_THRESHOLDS['impact_score']['reviews'],
            'issues': CURRENT_THRESHOLDS['impact_score']['issues'],
            'repos_impact': CURRENT_THRESHOLDS['impact_score']['repos_impact'],
            'consistency': CURRENT_THRESHOLDS['impact_score']['consistency']
        })
        
        # Create a dataframe for comparison
        comparison = pd.DataFrame({
            'Current Weights': current_weights,
            'Linear Regression': normalized_coefs,
            'Random Forest': rf_importance
        })
        
        # Plot comparison
        plt.figure(figsize=(12, 8))
        comparison.plot(kind='bar')
        plt.title('Comparison of Current vs. Data-Driven Weights')
        plt.ylabel('Weight / Importance')
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, 'weight_comparison.png'))
        
        # Calculate recommended weights based on average of LR and RF
        recommended_weights = (normalized_coefs + rf_importance) / 2
        recommended_weights = recommended_weights / recommended_weights.sum()
        
        comparison['Recommended'] = recommended_weights
        
        print("\nImpact Score Weight Analysis:")
        print(comparison)
        print("\nRecommended Weights:")
        for metric, weight in recommended_weights.items():
            print(f"{metric}: {weight:.3f}")
            
        return recommended_weights
    
    def analyze_repo_impact_factors(self):
        """Analyze repository impact factors."""
        if self.joined_repos is None:
            self.load_data()
            
        # Analyze technical vs ecosystem impact
        tech_impact = self.joined_repos['repo_tech_impact']
        eco_impact = self.joined_repos['repo_eco_impact']
        repo_impact = self.joined_repos['repo_impact']
        
        # Create a linear model to find optimal weights
        X = pd.DataFrame({
            'tech_impact': tech_impact,
            'eco_impact': eco_impact
        })
        y = repo_impact
        
        # Add constant for intercept
        X_sm = sm.add_constant(X)
        
        # Fit model
        model = sm.OLS(y, X_sm).fit()
        
        # Get coefficients
        coefs = model.params
        
        # Normalize to sum to 1 (excluding intercept)
        weights = coefs[1:] / coefs[1:].sum()
        
        print("\nRepository Impact Weight Analysis:")
        print(f"Current weights: Technical={CURRENT_THRESHOLDS['repo_impact']['technical']}, "
              f"Ecosystem={CURRENT_THRESHOLDS['repo_impact']['ecosystem']}")
        print(f"Data-driven weights: Technical={weights['tech_impact']:.2f}, "
              f"Ecosystem={weights['eco_impact']:.2f}")
        
        # Calculate correlation between technical and ecosystem impact
        corr = tech_impact.corr(eco_impact)
        print(f"Correlation between technical and ecosystem impact: {corr:.2f}")
        
        # Analyze PR acceptance and review activity weights
        # For this we'd need more detailed data, which might not be available
        # We can provide a placeholder recommendation based on available data
        
        return {
            'technical': weights['tech_impact'],
            'ecosystem': weights['eco_impact']
        }
    
    def analyze_contribution_ratio_exponent(self):
        """Analyze the contribution ratio exponent."""
        if self.joined_repos is None:
            self.load_data()
            
        # We need to see how contribution_ratio relates to repo_impact
        contribution_ratios = self.joined_repos['contribution_ratio']
        repo_impacts = self.joined_repos['repo_impact']
        
        # Create scatter plot
        plt.figure(figsize=(10, 6))
        plt.scatter(contribution_ratios, repo_impacts, alpha=0.5)
        
        # Try different exponents
        exponents = [0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        
        best_r2 = -1
        best_exponent = 0.7  # Current value
        
        for exp in exponents:
            # Create transformed feature
            X = pd.DataFrame({'contribution_ratio_exp': contribution_ratios ** exp})
            X = sm.add_constant(X)
            
            # Fit model
            model = sm.OLS(repo_impacts, X).fit()
            
            # Store R² value
            if model.rsquared > best_r2:
                best_r2 = model.rsquared
                best_exponent = exp
                
            # Plot fit line
            sorted_indices = np.argsort(contribution_ratios)
            sorted_x = np.array(contribution_ratios)[sorted_indices]
            sorted_x_exp = sorted_x ** exp
            x_for_plot = sm.add_constant(pd.DataFrame({'contribution_ratio_exp': sorted_x_exp}))
            predicted = model.predict(x_for_plot)
            
            plt.plot(sorted_x, predicted, label=f'Exponent={exp:.1f}, R²={model.rsquared:.3f}')
        
        plt.title('Contribution Ratio vs Repo Impact')
        plt.xlabel('Contribution Ratio')
        plt.ylabel('Repo Impact')
        plt.legend()
        plt.savefig(os.path.join(self.output_dir, 'contribution_ratio_analysis.png'))
        
        print(f"\nContribution Ratio Exponent Analysis:")
        print(f"Current exponent: {CURRENT_THRESHOLDS['contribution_ratio_exponent']}")
        print(f"Recommended exponent: {best_exponent} (R²={best_r2:.3f})")
        
        return best_exponent
    
    def analyze_collab_factor(self):
        """Analyze collaboration factor parameters."""
        if self.joined_repos is None:
            self.load_data()
            
        # Get collaborator counts
        collab_counts = self.joined_repos['collaborators']
        
        # Calculate current collab factor for each repository
        current_collab_factors = np.minimum(
            CURRENT_THRESHOLDS['collab_factor']['base'] + 
            np.log1p(collab_counts) * CURRENT_THRESHOLDS['collab_factor']['log_factor'],
            CURRENT_THRESHOLDS['collab_factor']['max_value']
        )
        
        # Try different parameters
        base_values = [0.8, 1.0, 1.2]
        log_factors = [0.3, 0.4, 0.5, 0.6]
        max_values = [2.0, 2.5, 3.0]
        
        # Grid search for optimal parameters
        results = []
        
        for base in base_values:
            for log_factor in log_factors:
                for max_val in max_values:
                    # Calculate collab factor
                    collab_factor = np.minimum(
                        base + np.log1p(collab_counts) * log_factor,
                        max_val
                    )
                    
                    # Calculate correlation with repo_impact
                    corr = np.corrcoef(collab_factor, self.joined_repos['repo_impact'])[0, 1]
                    
                    results.append({
                        'base': base,
                        'log_factor': log_factor,
                        'max_value': max_val,
                        'correlation': corr
                    })
        
        # Find best parameters
        results_df = pd.DataFrame(results)
        best_params = results_df.loc[results_df['correlation'].idxmax()]
        
        print("\nCollaboration Factor Analysis:")
        print(f"Current parameters: base={CURRENT_THRESHOLDS['collab_factor']['base']}, "
              f"log_factor={CURRENT_THRESHOLDS['collab_factor']['log_factor']}, "
              f"max_value={CURRENT_THRESHOLDS['collab_factor']['max_value']}")
        print(f"Recommended parameters: base={best_params['base']}, "
              f"log_factor={best_params['log_factor']}, "
              f"max_value={best_params['max_value']}")
        print(f"Improvement in correlation: {best_params['correlation'] - np.corrcoef(current_collab_factors, self.joined_repos['repo_impact'])[0, 1]:.3f}")
        
        return {
            'base': best_params['base'],
            'log_factor': best_params['log_factor'],
            'max_value': best_params['max_value']
        }
    
    def analyze_review_activity_normalization(self):
        """Analyze review activity normalization factor."""
        if self.joined_repos is None:
            self.load_data()
            
        # Get review comments
        review_comments = self.joined_repos['review_comments']
        
        # Plot distribution
        plt.figure(figsize=(10, 6))
        
        sns.histplot(review_comments, kde=True)
        plt.axvline(CURRENT_THRESHOLDS['review_activity']['normalization_factor'], 
                   color='r', linestyle='--', 
                   label=f"Current normalization factor: {CURRENT_THRESHOLDS['review_activity']['normalization_factor']}")
        
        # Add percentile lines
        p50 = np.percentile(review_comments, 50)
        p75 = np.percentile(review_comments, 75)
        p90 = np.percentile(review_comments, 90)
        
        plt.axvline(p50, color='green', linestyle=':', label=f'50th percentile: {p50:.1f}')
        plt.axvline(p75, color='orange', linestyle=':', label=f'75th percentile: {p75:.1f}')
        plt.axvline(p90, color='purple', linestyle=':', label=f'90th percentile: {p90:.1f}')
        
        plt.title('Distribution of Review Comments')
        plt.xlabel('Review Comments')
        plt.ylabel('Frequency')
        plt.legend()
        
        plt.savefig(os.path.join(self.output_dir, 'review_comments_distribution.png'))
        
        print("\nReview Activity Normalization Analysis:")
        print(f"Current normalization factor: {CURRENT_THRESHOLDS['review_activity']['normalization_factor']}")
        print(f"Percentiles: 50th={p50:.1f}, 75th={p75:.1f}, 90th={p90:.1f}")
        
        # Recommend the 75th percentile as normalization factor
        recommended = p75
        
        print(f"Recommended normalization factor: {recommended:.1f}")
        
        return recommended
    
    def generate_recommendations(self):
        """Generate final recommendations for all thresholds and constants."""
        if self.users is None:
            self.load_data()
            
        # Run all analyses
        normalization_thresholds = self.analyze_distributions()
        impact_weights = self.analyze_impact_weights()
        repo_impact_weights = self.analyze_repo_impact_factors()
        contribution_ratio_exponent = self.analyze_contribution_ratio_exponent()
        collab_factor_params = self.analyze_collab_factor()
        review_activity_normalization = self.analyze_review_activity_normalization()
        
        # Compile recommendations
        recommendations = {
            'normalization_thresholds': {
                metric: (min_val, max_val) for metric, (min_val, max_val) in normalization_thresholds.items()
            },
            'impact_score_weights': {
                metric: weight for metric, weight in impact_weights.items()
            },
            'repo_impact_weights': repo_impact_weights,
            'contribution_ratio_exponent': contribution_ratio_exponent,
            'collab_factor': collab_factor_params,
            'review_activity_normalization': review_activity_normalization
        }
        
        # Save recommendations to file
        import json
        with open(os.path.join(self.output_dir, 'recommendations.json'), 'w') as f:
            json.dump(recommendations, f, indent=2)
        
        return recommendations

def main():
    """Main function to run the analysis."""
    print("Starting threshold analysis...")
    
    analyzer = ThresholdAnalyzer()
    analyzer.load_data()
    recommendations = analyzer.generate_recommendations()
    
    print("\nAnalysis complete. Recommendations saved to results directory.")
    
if __name__ == "__main__":
    main() 