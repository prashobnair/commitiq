"""
Response Optimizer for API endpoints.

This module provides utilities to optimize and trim API response payloads,
reducing network transfer size and improving client-side performance.
"""

import logging
import json
import time
from typing import Dict, Any, List, Set, Union, Optional

# Get logger for this module
logger = logging.getLogger(__name__)

class ResponseOptimizer:
    """
    Utility class to optimize API response payloads by removing unnecessary
    data and optimizing data structures for transfer efficiency.
    """
    
    @staticmethod
    def optimize_analysis_response(
        analysis_data: Dict[str, Any], 
        minimal: bool = False,
        fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Optimize the GitHub analysis response payload.
        
        Args:
            analysis_data: The original analysis response data
            minimal: If True, returns only critical fields for minimal response
            fields: Optional list of specific fields to include
            
        Returns:
            Optimized response dictionary
        """
        start_time = time.time()
        if not analysis_data:
            return {}
            
        # Handle error responses - pass through unchanged
        if 'error' in analysis_data:
            return analysis_data
        
        # Create a new optimized response
        optimized = {
            'github_username': analysis_data.get('github_username', ''),
            'impact_score': float(analysis_data.get('impact_score', 0)),
        }
        
        # Include ID if it exists
        if 'id' in analysis_data:
            optimized['id'] = analysis_data['id']
            
        # If minimal mode is requested, return just the essential data
        if minimal:
            # Include only basic metrics for minimal mode
            if 'analysis' in analysis_data and isinstance(analysis_data['analysis'], dict):
                contributions = analysis_data['analysis'].get('contributions', {})
                optimized['metrics'] = {
                    'commits': int(contributions.get('commits', 0)),
                    'pulls': int(contributions.get('pulls', 0)),
                    'reviews': int(contributions.get('reviews', 0)),
                    'repos_impact': float(contributions.get('repos_impact', 0)),
                    'consistency': float(contributions.get('consistency', 0))
                }
            return optimized
            
        # For standard mode, include the essential analysis data with optimizations
        if 'analysis' in analysis_data and isinstance(analysis_data['analysis'], dict):
            analysis = analysis_data['analysis']
            
            # Create optimized analysis object
            optimized_analysis = {
                'username': analysis.get('username', ''),
            }
            
            # Include basic user attributes that are useful for display
            for field in ['name', 'avatarUrl', 'company', 'location']:
                if field in analysis and analysis[field]:
                    optimized_analysis[field] = analysis[field]
                    
            # Optimize followers/following - convert to integers
            if 'followers' in analysis:
                optimized_analysis['followers'] = int(analysis['followers'])
            if 'following' in analysis:
                optimized_analysis['following'] = int(analysis['following'])
                
            # Process contribution data
            if 'contributions' in analysis:
                contributions = analysis['contributions']
                optimized_contributions = {
                    'commits': int(contributions.get('commits', 0)),
                    'pulls': int(contributions.get('pulls', 0)),
                    'reviews': int(contributions.get('reviews', 0)),
                    'issues': int(contributions.get('issues', 0)),
                    'repos_impact': float(contributions.get('repos_impact', 0)),
                    'consistency': float(contributions.get('consistency', 0))
                }
                
                # Optimize top languages
                if 'top_languages' in contributions:
                    optimized_contributions['top_languages'] = [
                        {
                            'language': lang.get('language', ''),
                            'percentage': float(lang.get('percentage', 0))
                        }
                        for lang in contributions.get('top_languages', [])
                    ]
                
                # Optimize top repositories - keep only essential fields
                if 'top_repositories' in contributions:
                    optimized_contributions['top_repositories'] = []
                    for repo in contributions.get('top_repositories', []):
                        optimized_repo = {
                            'name': repo.get('name', ''),
                            'url': repo.get('url', ''),
                            'stars': int(repo.get('stars', 0)),
                            'forks': int(repo.get('forks', 0)),
                        }
                        
                        # Only include primaryLanguage if it exists and isn't N/A
                        if repo.get('primaryLanguage') and repo['primaryLanguage'] != 'N/A':
                            optimized_repo['primaryLanguage'] = repo['primaryLanguage']
                            
                        # Include impactScore as float
                        if 'impactScore' in repo:
                            optimized_repo['impactScore'] = float(repo['impactScore'])
                            
                        # Add contribution ratio if available
                        if 'contributionRatio' in repo:
                            optimized_repo['contributionRatio'] = float(repo['contributionRatio'])
                            
                        optimized_contributions['top_repositories'].append(optimized_repo)
                
                optimized_analysis['contributions'] = optimized_contributions
            
            optimized['analysis'] = optimized_analysis
            
        # Apply field filtering if specific fields are requested
        if fields:
            field_set = set(fields)
            filtered_response = {}
            
            # Helper function to filter nested dict based on field list
            def filter_dict(d, prefix=''):
                result = {}
                for key, value in d.items():
                    full_key = f"{prefix}.{key}" if prefix else key
                    
                    if full_key in field_set or key in field_set:
                        if isinstance(value, dict):
                            result[key] = filter_dict(value, full_key)
                        else:
                            result[key] = value
                return result
            
            # Apply filtering
            optimized = filter_dict(optimized)
            
        process_time = (time.time() - start_time) * 1000
        orig_size = len(json.dumps(analysis_data))
        opt_size = len(json.dumps(optimized))
        reduction = ((orig_size - opt_size) / orig_size) * 100 if orig_size > 0 else 0
        
        logger.debug(f"Response optimization: {orig_size} → {opt_size} bytes ({reduction:.1f}% reduction) in {process_time:.2f}ms")
        
        return optimized
    
    @staticmethod
    def optimize_report_response(report_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize report response data for downloading.
        
        Args:
            report_data: The original report data
            
        Returns:
            Optimized report response
        """
        if not report_data:
            return {}
            
        # For report downloads, keep essential fields and simplify structure
        optimized = {
            'github_username': report_data.get('github_username', ''),
            'impact_score': float(report_data.get('impact_score', 0)),
        }
        
        # Include analysis data with optimizations
        if 'analysis' in report_data and isinstance(report_data['analysis'], dict):
            # Use the same optimization logic as for analysis responses
            optimized['analysis'] = ResponseOptimizer.optimize_analysis_response(
                {'analysis': report_data['analysis']}, 
                minimal=False
            ).get('analysis', {})
            
        # Include analyzed_at if available
        if 'analyzed_at' in report_data and report_data['analyzed_at']:
            optimized['analyzed_at'] = report_data['analyzed_at']
            
        return optimized
    
    @staticmethod
    def get_etag_for_data(data: Dict[str, Any]) -> str:
        """
        Generate an ETag for the provided data.
        
        Args:
            data: The data to generate an ETag for
            
        Returns:
            str: ETag string
        """
        if not data:
            return ""
            
        # Use a simple hash-based approach for ETag generation
        serialized = json.dumps(data, sort_keys=True)
        return f'W/"{hash(serialized)}"'

# Create a singleton instance
response_optimizer = ResponseOptimizer() 