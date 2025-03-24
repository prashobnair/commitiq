#!/usr/bin/env python3
"""
Test script to validate the rounding issue with language percentages.
This script specifically tests the user fketelaars to validate the hypothesis
that language percentages add up to 99% instead of 100% due to integer rounding.
"""
import sys
import os
import json
from datetime import datetime

# Add the parent directory to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the analysis service
from app.utils.analysis_service import analysis_service
from app.utils import normalize_github_username


def test_language_percentages(username):
    """
    Test function to analyze the language percentages for a given GitHub username.
    
    Args:
        username (str): GitHub username to analyze
    
    Returns:
        dict: Analysis results with raw and rounded language percentages
    """
    print(f"Starting analysis for user: {username}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Normalize the username
    normalized_username = normalize_github_username(username)
    print(f"Normalized username: {normalized_username}")
    
    # Fetch GitHub data
    print("Fetching GitHub data...")
    github_data = analysis_service.fetch_all_data(normalized_username)
    
    if github_data.get('user') is None:
        print(f"Error: User {normalized_username} not found")
        return None
    
    if 'error' in github_data:
        print(f"Error during fetching: {github_data['error']}")
        return None
    
    # Aggregate the data
    print("Aggregating user data...")
    aggregated_data = analysis_service.aggregate_user_data(normalized_username, github_data)
    
    if 'error' in aggregated_data:
        print(f"Error during aggregation: {aggregated_data['error']}")
        return None
    
    # Extract the language percentages
    contributions = aggregated_data.get('contributions', {})
    top_languages = contributions.get('top_languages', [])
    
    # Print the language data
    print("\nLanguage percentages:")
    total_percentage = 0
    
    for lang in top_languages:
        lang_name = lang.get('language', 'Unknown')
        percentage = lang.get('percentage', 0)
        print(f"  {lang_name}: {percentage}%")
        total_percentage += percentage
    
    print(f"\nTotal percentage: {total_percentage}%")
    
    # Check if the total is 100%
    if abs(total_percentage - 100) < 0.01:
        print("✅ Total is 100% - No rounding issue")
    else:
        print(f"❌ Total is not 100% - Rounding issue detected: {total_percentage}%")
    
    # Analyze the rounding issue by recalculating from raw weights
    print("\nInvestigating potential rounding causes:")
    
    # Extract the language usage directly from the aggregated data before rounding
    # This would require modifying the analysis_service.py file to expose the raw weights
    # Instead, we'll simulate the issue by analyzing how different rounding methods impact the total
    
    # Let's assume the languages have these raw percentages (example)
    # Since we can't access the raw weights directly, these are hypothetical values
    hypothetical_raw_percentages = []
    
    # Create potential raw percentages that would round to the observed values
    for lang in top_languages:
        percentage = lang.get('percentage', 0)
        # Create a range of potential raw values that would round to this integer
        potential_raw = percentage + 0.5 - 1  # Start from the lowest value that rounds to percentage
        hypothetical_raw_percentages.append({
            'language': lang.get('language', 'Unknown'),
            'observed_percentage': percentage,
            'potential_raw_percentage': potential_raw
        })
    
    # Simulate different rounding methods
    print("\nSimulated rounding methods:")
    
    # 1. Raw percentages (hypothetical)
    print("Potential raw percentages:")
    total_raw = 0
    for lang in hypothetical_raw_percentages:
        print(f"  {lang['language']}: {lang['potential_raw_percentage']:.1f}%")
        total_raw += lang['potential_raw_percentage']
    print(f"  Total of raw percentages: {total_raw:.1f}%")
    
    # 2. Integer rounding (current method)
    print("\nInteger rounding (current method):")
    total_integer = 0
    for lang in hypothetical_raw_percentages:
        rounded = round(lang['potential_raw_percentage'])
        print(f"  {lang['language']}: {rounded}% (from {lang['potential_raw_percentage']:.1f}%)")
        total_integer += rounded
    print(f"  Total after integer rounding: {total_integer}%")
    
    # 3. Rounding with adjustment to ensure 100%
    print("\nRounding with adjustment:")
    # First, round down all percentages
    floor_values = []
    floor_total = 0
    for lang in hypothetical_raw_percentages:
        floor_value = int(lang['potential_raw_percentage'])
        floor_values.append({
            'language': lang['language'],
            'floor_value': floor_value,
            'remainder': lang['potential_raw_percentage'] - floor_value
        })
        floor_total += floor_value
    
    # Distribute the remaining percentage points based on decimal remainders
    remaining = 100 - floor_total
    adjusted_values = sorted(floor_values, key=lambda x: x['remainder'], reverse=True)
    
    # Distribute remaining points to those with highest remainders
    for i in range(remaining):
        if i < len(adjusted_values):
            adjusted_values[i]['floor_value'] += 1
    
    # Print final adjusted values
    total_adjusted = 0
    for lang in adjusted_values:
        print(f"  {lang['language']}: {lang['floor_value']}% (adjusted from {lang['floor_value'] - (1 if lang['remainder'] > adjusted_values[min(remaining, len(adjusted_values))-1]['remainder'] else 0)}%)")
        total_adjusted += lang['floor_value']
    print(f"  Total after adjustment: {total_adjusted}%")
    
    return {
        'username': normalized_username,
        'top_languages': top_languages,
        'total_percentage': total_percentage,
        'hypothetical_analysis': {
            'raw_total': total_raw,
            'integer_rounding_total': total_integer,
            'adjusted_rounding_total': total_adjusted
        }
    }


if __name__ == '__main__':
    # Test the language percentages for user fketelaars
    result = test_language_percentages('fketelaars')
    
    # Save the results to a JSON file for reference
    if result:
        output_file = os.path.join(os.path.dirname(__file__), 'language_rounding_results.json')
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"\nResults saved to {output_file}") 