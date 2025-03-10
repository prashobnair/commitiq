# GitHub User Metrics Data Collection

This directory contains scripts for collecting GitHub user metrics and storing them in a database.

## Setup

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Make sure you have access to the GitHub users database and the metrics database.

3. (Optional) Create a `.env` file from the template:

```bash
cp .env.template .env
```

Then edit the `.env` file with your PostgreSQL credentials and GitHub API token.

## Data Migration

To migrate data from SQLite to PostgreSQL, use the `run_migration.sh` script:

```bash
./run_migration.sh --pg-host <host> --pg-port <port> --pg-user <user> --pg-password <password> --pg-db <database>
```

If you've set up the `.env` file, you can simply run:

```bash
./run_migration.sh
```

Options:
- `--sqlite-db PATH`: Path to SQLite database (default: `data/metrics_analysis.db`)
- `--pg-host HOST`: PostgreSQL host (default: `localhost`)
- `--pg-port PORT`: PostgreSQL port (default: `5432`)
- `--pg-user USER`: PostgreSQL username (default: `postgres`)
- `--pg-password PASS`: PostgreSQL password
- `--pg-db DB`: PostgreSQL database name (default: `github_data`)
- `--batch-size NUM`: Batch size for data transfer (default: `1000`)
- `--debug`: Enable debug mode
- `--help`: Show help message

## Data Collection

### Using SQLite

To collect GitHub user metrics and store them in a SQLite database, use the `run_batch.sh` script:

```bash
./run_batch.sh --batch-size 100 --workers 16
```

### Using PostgreSQL

To collect GitHub user metrics and store them in a PostgreSQL database, use the `run_batch.sh` script with the `--use-postgres` flag:

```bash
./run_batch.sh --batch-size 100 --workers 16 --use-postgres --pg-host <host> --pg-port <port> --pg-user <user> --pg-password <password> --pg-db <database>
```

If you've set up the `.env` file, you can simply run:

```bash
./run_batch.sh --batch-size 100 --workers 16 --use-postgres
```

Options:
- `--batch-size NUM`: Number of users to process (default: `100`)
- `--workers NUM`: Number of parallel workers (default: `16`)
- `--github-db PATH`: Path to GitHub users database (default: `../github_user_db/data/github_users.db`)
- `--metrics-db PATH`: Path to metrics database (default: `data/metrics_analysis.db`)
- `--resume`: Resume from the last checkpoint
- `--debug`: Enable debug mode
- `--delay SECONDS`: Delay in seconds between batches (default: `10`)
- `--use-postgres`: Use PostgreSQL instead of SQLite
- `--pg-host HOST`: PostgreSQL host (default: `localhost`)
- `--pg-port PORT`: PostgreSQL port (default: `5432`)
- `--pg-user USER`: PostgreSQL username (default: `postgres`)
- `--pg-password PASS`: PostgreSQL password
- `--pg-db DB`: PostgreSQL database name (default: `github_data`)
- `--help`: Show help message

## Database Schema

### SQLite

The SQLite database has the following tables:
- `users`: User information
- `metrics`: User metrics
- `repositories`: Repository information

### PostgreSQL

The PostgreSQL database has the following tables:
- `score_users`: User information
- `score_metrics`: User metrics
- `score_repositories`: Repository information
- `github_users`: GitHub users (imported from SQLite)

## Output Files

The data collection process generates the following output files:
- `data/<username>_metrics.json`: Raw metrics data for each user
- `data/batch_summary.json`: Summary of the batch collection
- `data/batch_progress.json`: Progress of the batch collection
- `logs/batch_collection.log`: Log file for the batch collection
- `logs/migration_<timestamp>.log`: Log file for the migration 