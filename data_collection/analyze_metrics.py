#!/usr/bin/env python3
"""
GitHub User Metrics Analysis

This script analyzes the collected GitHub user metrics to generate normalization
constants and factors for the impact score calculation.
"""

import os
import sys
import json
import logging
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
import matplotlib.pyplot as plt
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / "metrics_analysis.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
METRICS_FILE = Path(__file__).parent / "data" / "user_metrics.json"
ANALYSIS_DIR = Path(__file__).parent / "data" / "analysis"
PERCENTILES = [5, 10, 25, 50, 75, 90, 95, 99]

# Core metrics to analyze
CORE_METRICS = [
    'pulls',
    'commits',
    'reviews',
    'issues',
    'repos_impact',
    'consistency'
]

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Analyze GitHub user metrics and generate normalization constants.')
    parser.add_argument('--visualize', action='store_true',
                        help='Generate visualizations of the metrics distributions')
    parser.add_argument('--output', type=str, default=None,
                        help='Output file for the normalization constants (default: auto-generated)')
    return parser.parse_args()

def load_metrics_data():
    """Load the collected metrics data."""
    if not METRICS_FILE.exists():
        logger.error(f"Metrics file not found at {METRICS_FILE}")
        sys.exit(1)
    
    try:
        with open(METRICS_FILE, 'r') as f:
            data = json.load(f)
        
        # Filter out error results
        successful_data = [d for d in data if d.get('status') == 'success']
        
        logger.info(f"Loaded {len(successful_data)} successful results out of {len(data)} total")
        return successful_data
    
    except Exception as e:
        logger.error(f"Error loading metrics data: {str(e)}")
        sys.exit(1)

def extract_metrics_dataframe(data):
    """
    Extract metrics from the raw data into a pandas DataFrame.
    
    Args:
        data: List of user metrics dictionaries
        
    Returns:
        DataFrame with extracted metrics
    """
    # Extract core metrics
    metrics_data = []
    
    for user_data in data:
        user_metrics = {
            'username': user_data.get('username'),
            'user_id': user_data.get('user_id'),
            'impact_score': user_data.get('impact_score', 0)
        }
        
        # Extract contribution metrics
        contributions = user_data.get('contributions', {})
        for metric in CORE_METRICS:
            user_metrics[metric] = contributions.get(metric, 0)
        
        # Extract repository metrics
        metrics = user_data.get('metrics', {})
        user_metrics['repo_count'] = len(metrics.get('repositories', []))
        
        # Add to the list
        metrics_data.append(user_metrics)
    
    # Convert to DataFrame
    df = pd.DataFrame(metrics_data)
    
    return df

def analyze_metrics(df):
    """
    Analyze metrics and generate statistics.
    
    Args:
        df: DataFrame with metrics
        
    Returns:
        Dictionary with analysis results
    """
    analysis = {
        'timestamp': datetime.now().isoformat(),
        'sample_size': len(df),
        'metrics': {},
        'correlations': {},
        'percentiles': {},
        'suggested_normalization': {}
    }
    
    # Basic statistics for each metric
    for metric in CORE_METRICS + ['impact_score', 'repo_count']:
        metric_stats = df[metric].describe().to_dict()
        analysis['metrics'][metric] = metric_stats
    
    # Calculate percentiles for each metric
    for metric in CORE_METRICS + ['impact_score']:
        percentile_values = np.percentile(df[metric], PERCENTILES)
        analysis['percentiles'][metric] = {
            f'p{p}': float(v) for p, v in zip(PERCENTILES, percentile_values)
        }
    
    # Calculate correlations with impact score
    for metric in CORE_METRICS:
        correlation = df[metric].corr(df['impact_score'])
        analysis['correlations'][metric] = float(correlation)
    
    # Generate suggested normalization thresholds
    for metric in CORE_METRICS:
        # Use p10 as lower bound and p95 as upper bound
        lower_bound = analysis['percentiles'][metric]['p10']
        upper_bound = analysis['percentiles'][metric]['p95']
        
        # Round to appropriate precision
        if metric in ['consistency']:
            # Consistency is a ratio, keep more precision
            lower_bound = round(lower_bound, 3)
            upper_bound = round(upper_bound, 3)
        else:
            # Integer metrics
            lower_bound = max(1, int(round(lower_bound)))
            upper_bound = max(lower_bound + 1, int(round(upper_bound)))
        
        analysis['suggested_normalization'][metric] = [lower_bound, upper_bound]
    
    return analysis

def generate_visualizations(df, analysis):
    """
    Generate visualizations of the metrics distributions.
    
    Args:
        df: DataFrame with metrics
        analysis: Analysis results dictionary
    """
    # Create output directory
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    
    # Set up the plots
    plt.style.use('ggplot')
    
    # 1. Distribution of impact scores
    plt.figure(figsize=(10, 6))
    plt.hist(df['impact_score'], bins=20, alpha=0.7, color='blue')
    plt.axvline(analysis['metrics']['impact_score']['mean'], color='red', linestyle='dashed', linewidth=1)
    plt.title('Distribution of Impact Scores')
    plt.xlabel('Impact Score')
    plt.ylabel('Frequency')
    plt.savefig(ANALYSIS_DIR / 'impact_score_distribution.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 2. Correlation matrix
    corr_metrics = CORE_METRICS + ['impact_score']
    corr_matrix = df[corr_metrics].corr()
    
    plt.figure(figsize=(10, 8))
    plt.matshow(corr_matrix, fignum=1, cmap='coolwarm')
    plt.colorbar()
    plt.xticks(range(len(corr_metrics)), corr_metrics, rotation=45)
    plt.yticks(range(len(corr_metrics)), corr_metrics)
    plt.title('Correlation Matrix of Metrics')
    
    # Add correlation values
    for i in range(len(corr_metrics)):
        for j in range(len(corr_metrics)):
            plt.text(i, j, f'{corr_matrix.iloc[i, j]:.2f}', ha='center', va='center', 
                     color='white' if abs(corr_matrix.iloc[i, j]) > 0.5 else 'black')
    
    plt.savefig(ANALYSIS_DIR / 'correlation_matrix.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    # 3. Individual metric distributions
    for metric in CORE_METRICS:
        plt.figure(figsize=(10, 6))
        
        # Plot histogram
        plt.hist(df[metric], bins=20, alpha=0.7, color='blue')
        
        # Add vertical lines for percentiles
        for percentile in [10, 50, 90]:
            value = analysis['percentiles'][metric][f'p{percentile}']
            plt.axvline(value, color='red', linestyle='dashed', linewidth=1)
            plt.text(value, plt.ylim()[1]*0.9, f'P{percentile}: {value:.1f}', 
                     rotation=90, verticalalignment='top')
        
        # Add suggested normalization bounds
        lower, upper = analysis['suggested_normalization'][metric]
        plt.axvspan(lower, upper, alpha=0.2, color='green')
        plt.text((lower + upper)/2, plt.ylim()[1]*0.8, 'Suggested Range', 
                 ha='center', va='center', bbox=dict(facecolor='white', alpha=0.5))
        
        plt.title(f'Distribution of {metric.capitalize()}')
        plt.xlabel(metric.capitalize())
        plt.ylabel('Frequency')
        plt.savefig(ANALYSIS_DIR / f'{metric}_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    # 4. Scatter plots against impact score
    for metric in CORE_METRICS:
        plt.figure(figsize=(10, 6))
        plt.scatter(df[metric], df['impact_score'], alpha=0.5)
        
        # Add correlation coefficient
        corr = analysis['correlations'][metric]
        plt.text(0.05, 0.95, f'Correlation: {corr:.3f}', transform=plt.gca().transAxes,
                 bbox=dict(facecolor='white', alpha=0.5))
        
        plt.title(f'{metric.capitalize()} vs Impact Score')
        plt.xlabel(metric.capitalize())
        plt.ylabel('Impact Score')
        plt.savefig(ANALYSIS_DIR / f'{metric}_vs_impact.png', dpi=300, bbox_inches='tight')
        plt.close()
    
    logger.info(f"Visualizations saved to {ANALYSIS_DIR}")

def generate_normalization_constants(analysis, output_file=None):
    """
    Generate normalization constants file based on the analysis.
    
    Args:
        analysis: Analysis results dictionary
        output_file: Optional output file path
    """
    # Create output file name if not provided
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = ANALYSIS_DIR / f'normalization_constants_{timestamp}.py'
    else:
        output_file = Path(output_file)
    
    # Create parent directory if it doesn't exist
    os.makedirs(output_file.parent, exist_ok=True)
    
    # Format the constants
    constants_code = f"""# Normalization constants generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Based on analysis of {analysis['sample_size']} GitHub users

# Normalization thresholds (min, max) for percentile-based normalization
NORMALIZATION_THRESHOLDS = {{
"""
    
    # Add each metric's normalization thresholds
    for metric, values in analysis['suggested_normalization'].items():
        constants_code += f"    '{metric}': {values},\n"
    
    # Close the dictionary and add a comment about the weights
    constants_code += """}

# These weights are from the original implementation
# You may want to adjust these based on the correlation analysis
IMPACT_SCORE_WEIGHTS = {
    'pulls': 0.27,
    'commits': 0.225,
    'reviews': 0.135,
    'issues': 0.09,
    'repos_impact': 0.18,
    'consistency': 0.10
}

# Correlation with impact score from analysis
METRIC_CORRELATIONS = {
"""
    
    # Add correlations
    for metric, value in analysis['correlations'].items():
        constants_code += f"    '{metric}': {value:.3f},\n"
    
    constants_code += "}\n"
    
    # Write to file
    with open(output_file, 'w') as f:
        f.write(constants_code)
    
    logger.info(f"Normalization constants saved to {output_file}")
    return output_file

def main():
    """Main function to analyze metrics and generate normalization constants."""
    args = parse_args()
    
    # Create analysis directory if it doesn't exist
    os.makedirs(ANALYSIS_DIR, exist_ok=True)
    
    # Load metrics data
    data = load_metrics_data()
    
    # Extract metrics into DataFrame
    df = extract_metrics_dataframe(data)
    
    # Analyze metrics
    analysis = analyze_metrics(df)
    
    # Save analysis results
    analysis_file = ANALYSIS_DIR / f'metrics_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(analysis_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    logger.info(f"Analysis results saved to {analysis_file}")
    
    # Generate visualizations if requested
    if args.visualize:
        generate_visualizations(df, analysis)
    
    # Generate normalization constants
    constants_file = generate_normalization_constants(analysis, args.output)
    
    # Print summary
    print("\n=== GitHub User Metrics Analysis Summary ===\n")
    print(f"Analyzed {analysis['sample_size']} users")
    print("\nSuggested Normalization Thresholds:")
    for metric, values in analysis['suggested_normalization'].items():
        print(f"  - {metric}: {values}")
    
    print("\nMetric Correlations with Impact Score:")
    for metric, value in sorted(analysis['correlations'].items(), key=lambda x: abs(x[1]), reverse=True):
        print(f"  - {metric}: {value:.3f}")
    
    print(f"\nAnalysis results saved to: {analysis_file}")
    if args.visualize:
        print(f"Visualizations saved to: {ANALYSIS_DIR}")
    print(f"Normalization constants saved to: {constants_file}")

if __name__ == "__main__":
    main() 