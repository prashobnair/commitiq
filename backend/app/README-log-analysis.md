# CommitIQ Log Analysis Guide

This guide explains how to use the log analysis tools provided with CommitIQ to monitor application health, troubleshoot issues, and understand usage patterns.

## Log Files Location

Application logs are stored in the `backend/logs/` directory:

- `commitiq.log` - Main application log (rotated when it reaches 10MB)
- `commitiq.log.1`, `commitiq.log.2`, etc. - Rotated log files
- `debug.log` - More detailed log for debugging purposes

## Log Format

Each log entry follows this format:

```
YYYY-MM-DD HH:MM:SS - module.name - LEVEL - filename.py:line_number - Message
```

For example:
```
2023-12-15 14:32:47 - app.api.analysis - INFO - analysis.py:163 - Analyzing user input: octocat from IP: 127.0.0.1
```

## Log Analyzer Tool

We provide a powerful log analyzer tool that can help you extract insights from the application logs. The analyzer can:

- Generate summaries of application usage
- Find the most common errors
- Detect patterns of suspicious activity
- Track user behavior
- Identify recurring errors that need fixing

### Basic Usage

```bash
# Show a basic summary of the logs
python backend/app/log_analyzer.py

# Analyze a specific log file
python backend/app/log_analyzer.py --file=backend/logs/commitiq.log.1

# Show only errors and exceptions
python backend/app/log_analyzer.py --errors-only

# Show logs since a specific date
python backend/app/log_analyzer.py --since=2023-12-01

# Show the top 10 most common errors
python backend/app/log_analyzer.py --errors=10

# Show the top 20 most active users
python backend/app/log_analyzer.py --users=20

# Output results in JSON format for further processing
python backend/app/log_analyzer.py --summary --json > log_summary.json
```

### Advanced Analysis

```bash
# Find recurring errors (appearing 3+ times)
python backend/app/log_analyzer.py --recurring

# Detect suspicious activity patterns
python backend/app/log_analyzer.py --suspicious

# Filter logs containing a specific string
python backend/app/log_analyzer.py --filter="GitHub API rate limit"
```

## Common Error Types and Resolution

Here are some common error types you might see in the logs and how to resolve them:

1. **GitHub API Rate Limit Errors**
   - Message: `GitHub API rate limit exceeded` or `Rate limit reached`
   - Resolution: Ensure your GitHub API token is valid and has sufficient permissions. Consider using a token with higher rate limits.

2. **Username Not Found Errors**
   - Message: `User not found in GitHub` or `Username not found`
   - Resolution: These are normal errors when users enter invalid GitHub usernames. No action needed.

3. **Database Connection Errors**
   - Message: `Database connection error`
   - Resolution: Check that PostgreSQL is running and the connection parameters in `.env` are correct.

4. **Invalid Response Format**
   - Message: `Invalid GitHub API response format`
   - Resolution: May indicate an issue with the GitHub API or a change in its response format. Check for GitHub API updates.

5. **Authentication Errors**
   - Message: `Unable to access profile data`
   - Resolution: Verify that your GitHub token has the necessary permissions and is not expired.

## Monitoring Health

You can use the log analyzer to set up a regular health check:

```bash
# Create a daily health report
python backend/app/log_analyzer.py --summary --json > "reports/health_$(date +%Y-%m-%d).json"

# Alert on high error rates (example using jq)
python backend/app/log_analyzer.py --summary --json | jq '.requests.success_rate_percent < 90' | grep -q true && echo "Alert: High error rate!" | mail -s "CommitIQ Health Alert" admin@example.com
```

## Best Practices

1. **Review logs regularly** - Set up a schedule to review logs at least once a week to catch recurring issues.

2. **Monitor error rates** - A sudden increase in errors could indicate a problem with the application or an external service.

3. **Keep track of suspicious activity** - Use the `--suspicious` flag to detect potential abuse or misconfiguration.

4. **Archive old logs** - Set up a process to archive older log files to prevent disk space issues.

5. **Set up alerts** - Configure alerts for critical error conditions to be notified immediately.

## Extending the Analyzer

The log analyzer is designed to be extensible. If you need to add new analysis capabilities:

1. Open `backend/app/log_analyzer.py`
2. Add new methods to the `LogAnalyzer` class for your specific analysis needs
3. Update the command-line arguments in `parse_args()` to include your new options
4. Add handling for your new options in the `main()` function

# Error Tracking Module

In addition to the log analyzer, CommitIQ includes an `error_tracker` module that provides a standardized way to log errors across the application. This module ensures that all errors are logged with sufficient context for effective debugging.

## Using the Error Tracker

The `error_tracker` module provides three main functions:

1. **track_errors** - A decorator that logs errors and re-raises them
2. **handle_errors** - A decorator that logs errors and returns a default value
3. **log_error** - A function for manually logging errors with context

### Examples

#### Track Errors Decorator

```python
from app.utils.error_tracker import track_errors

@track_errors
def process_github_data(username, data):
    # This function will automatically log any errors with context
    # about the function arguments, then re-raise the exception
    result = data['repository']  # Will log and raise KeyError if missing
    return result
```

#### Handle Errors Decorator

```python
from app.utils.error_tracker import handle_errors

@handle_errors(default_return={"error": "Failed to process data"})
def get_user_stats(username):
    # This function will log errors but return the default value
    # instead of raising exceptions
    if not username:
        raise ValueError("Username cannot be empty")
    
    # Process user stats...
    return {"stats": "processed"}
```

#### Manual Error Logging

```python
from app.utils.error_tracker import log_error

def api_endpoint(request):
    try:
        # Process API request...
        result = process_data(request.json)
        return result
    except Exception as e:
        # Manually log the error with context
        log_error(
            error=e,
            context={"request_data": str(request.json)},
            user_info={
                "username": request.json.get("username"),
                "ip": request.remote_addr
            }
        )
        # Return an error response
        return {"error": "An error occurred processing your request"}
```

## Best Practices for Error Tracking

1. **Use descriptive error messages** - Make sure error messages clearly describe what went wrong.

2. **Include relevant context** - Always include data that would help diagnose the problem, such as user IDs, input values, or system state.

3. **Track user information** - When possible, include user information (username, IP) to help trace issues to specific users or sessions.

4. **Categorize errors** - Use consistent error types to help with aggregation and analysis.

5. **Handle sensitive data** - Ensure sensitive information like passwords or tokens is not included in logs.

6. **Use appropriate log levels** - Use ERROR for actual errors and WARNING for potential issues.

For complete examples, see `backend/app/utils/error_tracker_example.py` 