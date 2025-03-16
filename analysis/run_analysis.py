#!/usr/bin/env python3
"""
Main script to run the GitHub impact score analysis.
"""
import os
import sys
import logging
from datetime import datetime

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

from threshold_analyzer import ThresholdAnalyzer

def setup_logging():
    """Configure logging for the analysis."""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'analysis_{timestamp}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger('impact_score_analysis')

def main():
    """Main entry point for the analysis."""
    logger = setup_logging()
    
    logger.info("=" * 80)
    logger.info("Starting GitHub Impact Score Analysis")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    try:
        # Set results directory
        results_dir = os.path.join(os.path.dirname(__file__), 'results', 
                                 datetime.now().strftime('%Y%m%d_%H%M%S'))
        
        # Create analyzer instance
        analyzer = ThresholdAnalyzer(output_dir=results_dir)
        
        # Load data
        logger.info("Loading data from database...")
        analyzer.load_data()
        
        # Run analysis and generate recommendations
        logger.info("Generating recommendations based on data analysis...")
        recommendations = analyzer.generate_recommendations()
        
        logger.info(f"Analysis complete. Results saved to: {results_dir}")
        
        # Print summary of recommendations
        logger.info("\nSUMMARY OF RECOMMENDATIONS:")
        
        for category, values in recommendations.items():
            logger.info(f"\n{category.upper()}:")
            
            if isinstance(values, dict):
                for key, value in values.items():
                    logger.info(f"  {key}: {value}")
            else:
                logger.info(f"  {values}")
                
    except Exception as e:
        logger.error(f"Error during analysis: {str(e)}", exc_info=True)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main()) 