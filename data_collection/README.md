# GitHub User Metrics Collection System

This system collects GitHub metrics for a sample of users from the database, processes them in parallel, and stores the results for normalization analysis.

## Overview

The goal of this system is to collect metrics for 10,000 GitHub users from a database of 7.2 million users, analyze the data to determine appropriate normalization constants and factors for the impact score calculation, and store the results in a database for further analysis.

## Components

The system consists of the following components:

1. **Data Collection** (`collect_metrics.py`): Samples users from the database with a distribution favoring later users, fetches GitHub data for each user, and calculates metrics using the existing `aggregate_user_data` function.

2. **Metrics Analysis** (`analyze_metrics.py`): Analyzes the collected metrics to generate statistics, visualizations, and suggested normalization constants.

3. **Database Storage** (`db_storage.py`): Stores the collected metrics in a SQLite database for further analysis.

## Usage

### Prerequisites

- Python 3.7+
- Access to the GitHub user database
- GitHub API tokens (set in environment variables)

### Installation

1. Install the required dependencies:

```bash
pip install numpy pandas matplotlib
```

2. Ensure the GitHub user database exists at `../github_user_db/data/github_users.db`.

### Data Collection

To collect metrics for 10,000 GitHub users:

```bash
python collect_metrics.py --sample-size 10000 --workers 32
```

Options:
- `--sample-size`: Number of users to sample (default: 10000)
- `--workers`: Number of parallel workers (default: min(32, CPU_COUNT*2))
- `--resume`: Resume from the last checkpoint
- `--test`: Run in test mode with a small sample

The results will be saved to `data/user_metrics.json`.

### Metrics Analysis

To analyze the collected metrics and generate normalization constants:

```bash
python analyze_metrics.py --visualize
```

Options:
- `--visualize`: Generate visualizations of the metrics distributions
- `--output`: Output file for the normalization constants (default: auto-generated)

The analysis results will be saved to `data/analysis/metrics_analysis_TIMESTAMP.json` and the suggested normalization constants to `data/analysis/normalization_constants_TIMESTAMP.py`.

### Database Storage

To store the collected metrics in a database:

```bash
python db_storage.py --overwrite
```

Options:
- `--input`: Input metrics JSON file (default: `data/user_metrics.json`)
- `--db`: Output database file (default: `data/metrics_analysis.db`)
- `--overwrite`: Overwrite existing database

## Data Distribution Strategy

The system samples users from the database with a distribution favoring later users. This is achieved by dividing the user ID range into segments and sampling more users from later segments. This approach ensures that we get a representative sample of GitHub users, with more emphasis on more recent users who are likely to be more active.

## Parallel Processing

The system uses Python's `ProcessPoolExecutor` to process users in parallel, which significantly speeds up the data collection process. The number of parallel workers can be configured using the `--workers` option.

## Error Handling and Resumability

The system includes robust error handling and the ability to resume from the last checkpoint. If the data collection process is interrupted, it can be resumed using the `--resume` option.

## Output

The system generates the following outputs:

1. **Metrics Data** (`data/user_metrics.json`): Raw metrics data for each user.
2. **Analysis Results** (`data/analysis/metrics_analysis_TIMESTAMP.json`): Statistics and analysis of the collected metrics.
3. **Normalization Constants** (`data/analysis/normalization_constants_TIMESTAMP.py`): Suggested normalization constants for the impact score calculation.
4. **Visualizations** (`data/analysis/*.png`): Visualizations of the metrics distributions.
5. **Database** (`data/metrics_analysis.db`): SQLite database with the collected metrics.

## Logs

Logs are saved to the `logs` directory:
- `logs/metrics_collection.log`: Logs for the data collection process.
- `logs/metrics_analysis.log`: Logs for the metrics analysis process.
- `logs/db_storage.log`: Logs for the database storage process. 