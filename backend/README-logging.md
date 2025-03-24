# CommitIQ Logging Configuration

This document explains how logging is configured in the CommitIQ application, with a focus on how console logs are suppressed in production environments.

## Logging Overview

The CommitIQ application uses a centralized logging configuration that dynamically adapts based on the environment:

- **Production Environment**: Console logs are completely disabled to improve performance and security. All logs are redirected to log files and (optionally) external logging services.
- **Development/Testing/Staging**: Full console logging is enabled for improved developer experience.

## Environment Detection

The application detects the environment through the `FLASK_ENV` environment variable:

```bash
# For development (default if not set)
export FLASK_ENV=development

# For production (suppresses console logs)
export FLASK_ENV=production
```

## Using the Logging System

### Basic Logging

Import and use the standard Python logging module:

```python
import logging

# Get a logger for your module
logger = logging.getLogger(__name__)

# Log at different levels
logger.debug("Detailed debug information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical error")
```

### Enhanced Error Logging

For more comprehensive error logging with context:

```python
from app.utils.logger_config import log_error

try:
    # code that might fail
    result = 1 / 0
except Exception as e:
    log_error(e, context={"operation": "division", "input": 0})
```

### Logging Decorator

Use the decorator to automatically log errors in functions:

```python
from app.utils.logger_config import with_error_logging

@with_error_logging
def risky_operation(value):
    return 1 / value
```

## Log File Locations

Logs are stored in the following locations:

- **Regular Logs**: `backend/logs/app.log`
- **Error Logs**: `backend/logs/error.log`

All log files are automatically rotated when they reach 10MB, with 10 backup files kept.

## Testing the Logging Configuration

You can test how logging behaves in different environments using the provided test script:

```bash
# Test in development mode
cd backend
python test_logging.py

# Test in production mode
cd backend
FLASK_ENV=production python test_logging.py
```

You can also use the Flask CLI command:

```bash
# Test in development mode
cd backend
flask test-logging

# Test in production mode
cd backend
FLASK_ENV=production flask test-logging
```

## Extending the Logging System

### Adding External Logging Services

To add external logging services (like Sentry), update the `LoggerManager.configure()` method in `app/utils/logger_config.py`.

### Customizing Log Formats

Log formats can be customized by modifying the formatters in the `LoggerManager.get_logging_config()` method.

## Troubleshooting

If you're not seeing logs where expected:

1. Check the environment variables: `echo $FLASK_ENV`
2. Verify log directory permissions: `ls -la backend/logs`
3. Check log file contents: `tail -f backend/logs/app.log`

For production environments, remember that console logs are intentionally suppressed - all logs will be stored in log files only. 