# GitHub User Database

A tool for efficiently collecting and storing basic GitHub user data while respecting GitHub API rate limits.

## Features

- Collects basic GitHub user information (ID, login, type, etc.)
- Respects GitHub API rate limits
- Supports parallel processing for faster collection
- Resumable operations (can be stopped and restarted)
- Uses SQLite for simple, portable storage

## Requirements

- Python 3.7+
- Required packages (see `requirements.txt`)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/commitiq.git
   cd commitiq/github_user_db
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up GitHub API token (optional but recommended):
   
   Create a `.env` file in the project directory with your GitHub token:
   ```
   GITHUB_TOKEN=your_github_personal_access_token
   ```
   
   Without a token, you'll be limited to 60 requests per hour. With a token, you get 5,000 requests per hour.

## Usage

Run the collection script:

```bash
python collect_users.py
```

### Command-line Options

- `--since ID`: User ID to start from (default: resume from last run)
- `--workers N`: Number of parallel workers (default: 5)
- `--batch-size N`: Number of users per API request (default: 100, max: 100)
- `--max-batches N`: Maximum number of batches to fetch (default: unlimited)
- `--report-interval N`: Interval in seconds to report progress (default: 10)

### Examples

Start collection from the beginning:
```bash
python collect_users.py --since 0
```

Resume from where the last run left off:
```bash
python collect_users.py
```

Use 10 parallel workers:
```bash
python collect_users.py --workers 10
```

Collect only 50 batches (for testing):
```bash
python collect_users.py --max-batches 50
```

## Database

The collected data is stored in a SQLite database at `data/github_users.db`. The database contains:

- `github_users` table: Stores user information
- `sync_status` table: Tracks collection progress

You can access the database directly using SQLite tools:

```bash
sqlite3 data/github_users.db
```

## Performance Considerations

- The script is designed to be efficient while respecting GitHub's rate limits
- With a GitHub token, you can collect up to 5,000 users per hour
- The parallel processing feature helps maximize throughput
- The script can be safely interrupted and resumed at any time

## License

[MIT License](LICENSE) 