#!/usr/bin/env python3
"""
Test script for the GitHub User Metrics Collection System.

This script tests the data collection system with a small sample of users.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_command(command):
    """Run a command and log the output."""
    logger.info(f"Running command: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        logger.info(f"Command completed successfully")
        logger.debug(f"Output: {result.stdout}")
        
        return True
    
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with exit code {e.returncode}")
        logger.error(f"Error output: {e.stderr}")
        
        return False

def test_data_collection():
    """Test the data collection process."""
    logger.info("Testing data collection...")
    
    # Run the data collection script with a small sample
    success = run_command("python collect_metrics.py --test --workers 2")
    
    if not success:
        logger.error("Data collection test failed")
        return False
    
    # Check if the output file exists
    metrics_file = Path(__file__).parent / "data" / "user_metrics.json"
    if not metrics_file.exists():
        logger.error(f"Output file not found: {metrics_file}")
        return False
    
    logger.info("Data collection test passed")
    return True

def test_metrics_analysis():
    """Test the metrics analysis process."""
    logger.info("Testing metrics analysis...")
    
    # Run the metrics analysis script
    success = run_command("python analyze_metrics.py")
    
    if not success:
        logger.error("Metrics analysis test failed")
        return False
    
    # Check if the output directory exists
    analysis_dir = Path(__file__).parent / "data" / "analysis"
    if not analysis_dir.exists() or not any(analysis_dir.iterdir()):
        logger.error(f"Analysis output not found in: {analysis_dir}")
        return False
    
    logger.info("Metrics analysis test passed")
    return True

def test_db_storage():
    """Test the database storage process."""
    logger.info("Testing database storage...")
    
    # Run the database storage script
    success = run_command("python db_storage.py --overwrite")
    
    if not success:
        logger.error("Database storage test failed")
        return False
    
    # Check if the database file exists
    db_file = Path(__file__).parent / "data" / "metrics_analysis.db"
    if not db_file.exists():
        logger.error(f"Database file not found: {db_file}")
        return False
    
    logger.info("Database storage test passed")
    return True

def main():
    """Main function to run all tests."""
    logger.info("Starting system tests...")
    
    # Change to the script directory
    os.chdir(Path(__file__).parent)
    
    # Create data directory if it doesn't exist
    os.makedirs(Path(__file__).parent / "data", exist_ok=True)
    os.makedirs(Path(__file__).parent / "logs", exist_ok=True)
    
    # Run tests
    tests = [
        ("Data Collection", test_data_collection),
        ("Metrics Analysis", test_metrics_analysis),
        ("Database Storage", test_db_storage)
    ]
    
    all_passed = True
    
    for test_name, test_func in tests:
        logger.info(f"=== Running {test_name} Test ===")
        
        try:
            if not test_func():
                all_passed = False
                logger.error(f"{test_name} test failed")
            else:
                logger.info(f"{test_name} test passed")
        
        except Exception as e:
            all_passed = False
            logger.error(f"{test_name} test failed with exception: {str(e)}", exc_info=True)
        
        logger.info(f"=== {test_name} Test Completed ===\n")
    
    # Print summary
    if all_passed:
        logger.info("All tests passed!")
        return 0
    else:
        logger.error("Some tests failed. Check the logs for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 