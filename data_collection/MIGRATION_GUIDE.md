# Migration Guide: SQLite to PostgreSQL

This guide explains the changes made to migrate the GitHub user metrics data collection system from SQLite to PostgreSQL.

## Overview of Changes

1. **Database Migration Script**: Created a script (`migrate_to_rds.py`) to migrate data from SQLite to PostgreSQL.
2. **Database Utilities**: Created a module (`db_utils.py`) with utilities for connecting to both SQLite and PostgreSQL databases.
3. **Data Collection Script**: Updated the data collection script (`collect_batch.py`) to support both SQLite and PostgreSQL.
4. **Shell Scripts**: Updated the shell scripts (`run_batch.sh` and `run_migration.sh`) to support PostgreSQL connection parameters.
5. **Environment Variables**: Added support for loading PostgreSQL connection parameters from a `.env` file.

## Migration Process

### Step 1: Install Dependencies

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Step 2: Configure PostgreSQL Connection

Create a `.env` file from the template:

```bash
cp .env.template .env
```

Edit the `.env` file with your PostgreSQL credentials:

```
PG_HOST=your_postgres_host
PG_PORT=5432
PG_USER=your_postgres_user
PG_PASSWORD=your_postgres_password
PG_DB=github_data
```

### Step 3: Run the Migration Script

Run the migration script to transfer data from SQLite to PostgreSQL:

```bash
./run_migration.sh
```

This will:
1. Connect to both the SQLite and PostgreSQL databases
2. Create the necessary tables in PostgreSQL (`score_users`, `score_metrics`, `score_repositories`)
3. Transfer the data from SQLite to PostgreSQL
4. Verify the migration was successful

### Step 4: Update Data Collection to Use PostgreSQL

Run the data collection script with the `--use-postgres` flag:

```bash
./run_batch.sh --batch-size 100 --workers 16 --use-postgres
```

This will:
1. Connect to the PostgreSQL database
2. Sample users from the `github_users` table in PostgreSQL
3. Collect GitHub metrics for the sampled users
4. Store the metrics in the PostgreSQL database

## Database Schema

### SQLite (Original)

- `users`: User information
- `metrics`: User metrics
- `repositories`: Repository information

### PostgreSQL (New)

- `score_users`: User information
- `score_metrics`: User metrics
- `score_repositories`: Repository information
- `github_users`: GitHub users (imported from SQLite)

## Troubleshooting

### Connection Issues

If you encounter connection issues with PostgreSQL, check:
1. The PostgreSQL server is running and accessible
2. The connection parameters in the `.env` file are correct
3. The user has the necessary permissions to access the database

### Migration Issues

If the migration fails:
1. Check the migration log file in the `logs` directory
2. Verify the SQLite database exists and is accessible
3. Ensure the PostgreSQL user has permission to create tables

### Data Collection Issues

If data collection fails:
1. Check the batch collection log file in the `logs` directory
2. Verify the PostgreSQL database is accessible
3. Ensure the `github_users` table exists in the PostgreSQL database 