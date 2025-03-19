# CommitIQ Test Suite

This directory contains comprehensive testing tools for verifying the functionality of the CommitIQ application.

## Overview

The test suite covers all major functionality of CommitIQ:

- **GitHub Username Analysis**: Tests for analyzing GitHub profiles, username normalization, and handling various formats
- **Database Capture**: Verification that analysis data is properly stored in the database
- **Waitlist Functionality**: Testing user waitlist registration and updates
- **Share & Download Features**: Tests for creating share links, viewing shared analyses, and downloading reports
- **Analytics Tracking**: Verification that user activities are properly tracked for analytics

## Setup

### Prerequisites

1. The CommitIQ backend server must be running locally
2. PostgreSQL database must be properly configured and accessible
3. Python 3.6+ with required dependencies installed

### Installation

Install the test dependencies:

```bash
pip install -r tests/requirements.txt
```

### Configuration

The test suite uses the following environment variables (with defaults):

- `TEST_API_URL`: URL of the API server (default: `http://localhost:5000/api`)
- `DB_HOST`: Database hostname (default: `localhost`)
- `DB_PORT`: Database port (default: `5432`)
- `DB_NAME`: Database name (default: `commitiq`)
- `DB_USER`: Database username (default: `postgres`)
- `DB_PASSWORD`: Database password (default: `postgres`)

You can set these in a `.env` file or export them in your shell.

## Running Tests

### Full Test Suite

To run the complete test suite:

```bash
python tests/test_suite.py
```

### Specific Modules

To run tests for a specific module:

```bash
python tests/test_suite.py --module=analysis
python tests/test_suite.py --module=waitlist
python tests/test_suite.py --module=share
python tests/test_suite.py --module=database
python tests/test_suite.py --module=tracking
```

### Verbose Output

For detailed test information, use the `--verbose` or `-v` flag:

```bash
python tests/test_suite.py --verbose
```

### List Available Tests

To see a list of all available tests:

```bash
python tests/test_suite.py --list
```

## Test Output

The test output includes:

1. A summary of the test configuration
2. Details for each test run (standard or verbose mode)
3. A summary of test results including:
   - Total tests run
   - Number of failures
   - Number of errors
   - Number of skipped tests

## Debugging Failed Tests

When a test fails, the output will include:

1. The name of the failed test
2. The assertion that failed
3. The expected and actual values
4. A traceback to locate the failure

In verbose mode (`-v`), you'll also see detailed logging information that can help diagnose issues.

## Clean Up

The test suite automatically cleans up test data from the database after running. 
This includes:
- Test waitlist entries
- Test analysis records

## Adding New Tests

To add new tests:

1. Identify the appropriate test class based on the functionality being tested
2. Add a new test method starting with `test_`
3. Include a docstring explaining what the test verifies
4. Follow the existing pattern of testing:
   - Setup test data
   - Call the API or function being tested
   - Assert the expected results
   - Verify database state if applicable

## Continuous Integration

These tests can be run as part of a CI/CD pipeline. Example GitHub Actions workflow:

```yaml
name: Run Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: commitiq_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
          
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          if [ -f tests/requirements.txt ]; then pip install -r tests/requirements.txt; fi
      - name: Start backend server
        run: |
          python backend/run.py &
          sleep 5  # Give the server time to start
      - name: Run tests
        run: python backend/tests/test_suite.py
        env:
          DB_NAME: commitiq_test
```

## Troubleshooting

Common issues:

1. **Server not running**: Ensure the CommitIQ API server is running before starting tests
2. **Database connection errors**: Check your database credentials and connectivity
3. **Rate limiting**: If tests fail due to GitHub API rate limiting, consider using mock responses
4. **Timeouts**: Some tests might time out if the server is under load, adjust the timeouts as needed 