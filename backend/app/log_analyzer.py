#!/usr/bin/env python3
"""
CommitIQ Log Analyzer

This script analyzes application log files to identify errors, track usage,
and generate reports for debugging and monitoring purposes.

Usage:
    python log_analyzer.py [options]

Options:
    --file=PATH         Path to the log file (default: ../logs/commitiq.log)
    --errors-only       Only show error and exception logs
    --summary           Show summary statistics
    --filter=STRING     Filter logs containing specified string
    --users=N           Show top N users by request count
    --errors=N          Show top N most common errors
    --since=TIMESTR     Only analyze logs since specified time (e.g. "2023-12-01")
    --json              Output in JSON format
    --help              Show this help message

Examples:
    python log_analyzer.py --summary
    python log_analyzer.py --errors-only --since="2023-12-01"
    python log_analyzer.py --users=10 --json
"""

import os
import re
import sys
import json
import argparse
from datetime import datetime, timedelta
from collections import Counter, defaultdict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('log_analyzer')

# Regular expressions for parsing log lines
LOG_PATTERN = re.compile(
    r'(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - '
    r'(?P<module>[\w\.]+) - '
    r'(?P<level>\w+) - '
    r'(?P<file>[\w\.]+):(?P<line>\d+) - '
    r'(?P<message>.*)'
)

# Patterns to extract usernames and IPs from log messages
USERNAME_PATTERN = re.compile(r'(username|user): ([a-zA-Z0-9_-]+)')
IP_PATTERN = re.compile(r'IP: ([0-9\.]+)')
ERROR_PATTERN = re.compile(r'[Ee]rror: (.*?)($|( from IP:| - ))')

class LogAnalyzer:
    """Analyzes application log files to extract useful information."""
    
    def __init__(self, log_file):
        """Initialize with path to log file."""
        self.log_file = log_file
        self.logs = []
        self.errors = []
        self.warnings = []
        self.exceptions = []
        self.users = Counter()  # username -> count
        self.user_ips = defaultdict(set)  # username -> set of IPs
        self.ip_users = defaultdict(set)  # IP -> set of usernames
        self.error_types = Counter()  # error message -> count
        self.hourly_requests = Counter()  # hour -> count
        self.successful_analyses = []
        self.failed_analyses = []
    
    def parse_logs(self, since=None, filter_str=None):
        """Parse the log file and extract relevant information."""
        logger.info(f"Parsing log file: {self.log_file}")
        
        if not os.path.exists(self.log_file):
            logger.error(f"Log file not found: {self.log_file}")
            return False
        
        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
                logger.info(f"Filtering logs since: {since_dt}")
            except ValueError:
                logger.error(f"Invalid date format: {since}")
                return False
        
        line_count = 0
        try:
            with open(self.log_file, 'r') as f:
                for line in f:
                    line_count += 1
                    if line_count % 10000 == 0:
                        logger.info(f"Processed {line_count} lines...")
                    
                    # Apply filter if specified
                    if filter_str and filter_str not in line:
                        continue
                    
                    match = LOG_PATTERN.match(line.strip())
                    if not match:
                        continue
                    
                    log_entry = match.groupdict()
                    
                    # Parse timestamp
                    try:
                        log_entry['timestamp'] = datetime.strptime(
                            log_entry['timestamp'], '%Y-%m-%d %H:%M:%S'
                        )
                    except ValueError:
                        continue
                    
                    # Apply time filter
                    if since_dt and log_entry['timestamp'] < since_dt:
                        continue
                    
                    # Add entry to logs list
                    self.logs.append(log_entry)
                    
                    # Record error logs
                    level = log_entry['level']
                    message = log_entry['message']
                    
                    if level == 'ERROR':
                        self.errors.append(log_entry)
                        
                        # Extract error type
                        error_match = ERROR_PATTERN.search(message)
                        if error_match:
                            error_msg = error_match.group(1).strip()
                            self.error_types[error_msg] += 1
                    
                    elif level == 'WARNING':
                        self.warnings.append(log_entry)
                    
                    elif 'Exception' in message or 'Traceback' in message:
                        self.exceptions.append(log_entry)
                    
                    # Record user activity
                    username_match = USERNAME_PATTERN.search(message)
                    ip_match = IP_PATTERN.search(message)
                    
                    if username_match:
                        username = username_match.group(2)
                        self.users[username] += 1
                        
                        if ip_match:
                            ip = ip_match.group(1)
                            self.user_ips[username].add(ip)
                            self.ip_users[ip].add(username)
                    
                    # Record hourly requests
                    if 'Analyzing user' in message:
                        hour = log_entry['timestamp'].replace(minute=0, second=0)
                        self.hourly_requests[hour] += 1
                        
                        # Record if analysis was successful or failed
                        if 'Analysis complete' in message and 'impact score' in message:
                            self.successful_analyses.append(log_entry)
                        elif 'Error during' in message or 'Exception in analyze_user' in message:
                            self.failed_analyses.append(log_entry)
                
                logger.info(f"Finished processing {line_count} lines")
                return True
        
        except Exception as e:
            logger.error(f"Error parsing log file: {str(e)}")
            return False
    
    def generate_summary(self):
        """Generate a summary of the log analysis."""
        if not self.logs:
            return {"error": "No logs parsed"}
        
        # Time range
        start_time = min(log['timestamp'] for log in self.logs)
        end_time = max(log['timestamp'] for log in self.logs)
        
        # Request statistics
        total_requests = sum(self.hourly_requests.values())
        successful = len(self.successful_analyses)
        failed = len(self.failed_analyses)
        success_rate = (successful / total_requests * 100) if total_requests > 0 else 0
        
        # Error statistics
        error_count = len(self.errors)
        warning_count = len(self.warnings)
        exception_count = len(self.exceptions)
        
        # User statistics
        total_users = len(self.users)
        total_ips = len(self.ip_users)
        
        # Top errors
        top_errors = self.error_types.most_common(10)
        
        # Hourly request rate
        hours_span = (end_time - start_time).total_seconds() / 3600
        hourly_rate = total_requests / hours_span if hours_span > 0 else 0
        
        return {
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration_hours": round(hours_span, 2)
            },
            "requests": {
                "total": total_requests,
                "successful": successful,
                "failed": failed,
                "success_rate_percent": round(success_rate, 2),
                "hourly_rate": round(hourly_rate, 2)
            },
            "logs": {
                "total": len(self.logs),
                "errors": error_count,
                "warnings": warning_count,
                "exceptions": exception_count
            },
            "users": {
                "total_users": total_users,
                "total_ips": total_ips,
                "top_users": self.users.most_common(5)
            },
            "errors": {
                "top_errors": top_errors
            }
        }
    
    def get_top_users(self, limit=10):
        """Get the most active users by request count."""
        return [
            {
                "username": username,
                "requests": count,
                "unique_ips": len(self.user_ips.get(username, []))
            }
            for username, count in self.users.most_common(limit)
        ]
    
    def get_top_errors(self, limit=10):
        """Get the most common error types."""
        return [
            {
                "error": error_msg,
                "count": count,
                "percentage": round(count / len(self.errors) * 100, 2) if self.errors else 0
            }
            for error_msg, count in self.error_types.most_common(limit)
        ]
    
    def get_error_logs(self):
        """Get all error and exception logs."""
        return sorted(
            self.errors + self.exceptions,
            key=lambda x: x['timestamp'],
            reverse=True
        )
    
    def detect_recurring_errors(self):
        """Detect recurring errors that might indicate system issues."""
        recurring_errors = []
        
        # Group errors by error message
        for error_msg, count in self.error_types.items():
            if count >= 3:  # Consider an error recurring if it appears 3+ times
                # Find examples of this error
                examples = [
                    log for log in self.errors 
                    if error_msg in log['message']
                ][:3]  # Limit to 3 examples
                
                recurring_errors.append({
                    "error_message": error_msg,
                    "count": count,
                    "examples": examples
                })
        
        return sorted(recurring_errors, key=lambda x: x['count'], reverse=True)
    
    def detect_suspicious_activity(self):
        """Detect potentially suspicious activity patterns."""
        suspicious = []
        
        # IPs accessing multiple user accounts
        for ip, usernames in self.ip_users.items():
            if len(usernames) > 5:  # An IP accessing many different usernames
                suspicious.append({
                    "type": "multiple_users_per_ip",
                    "ip": ip,
                    "user_count": len(usernames),
                    "users": list(usernames)[:10]  # Limit to 10 examples
                })
        
        # Users with high failure rates
        for username, count in self.users.items():
            if count < 5:  # Skip users with few requests
                continue
                
            failed_for_user = sum(
                1 for log in self.failed_analyses
                if username in log['message']
            )
            
            failure_rate = failed_for_user / count
            if failure_rate > 0.8:  # 80% or more requests failing
                suspicious.append({
                    "type": "high_failure_rate",
                    "username": username,
                    "requests": count,
                    "failed": failed_for_user,
                    "failure_rate": round(failure_rate * 100, 2)
                })
        
        return suspicious

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="CommitIQ Log Analyzer")
    parser.add_argument('--file', type=str, default="../logs/commitiq.log",
                        help="Path to the log file")
    parser.add_argument('--errors-only', action='store_true',
                        help="Only show error and exception logs")
    parser.add_argument('--summary', action='store_true',
                        help="Show summary statistics")
    parser.add_argument('--filter', type=str,
                        help="Filter logs containing specified string")
    parser.add_argument('--users', type=int, default=0,
                        help="Show top N users by request count")
    parser.add_argument('--errors', type=int, default=0,
                        help="Show top N most common errors")
    parser.add_argument('--since', type=str,
                        help="Only analyze logs since specified time (ISO format)")
    parser.add_argument('--json', action='store_true',
                        help="Output in JSON format")
    parser.add_argument('--recurring', action='store_true',
                        help="Show recurring errors")
    parser.add_argument('--suspicious', action='store_true',
                        help="Show suspicious activity")
    
    return parser.parse_args()

def print_json(data):
    """Print data as formatted JSON."""
    print(json.dumps(data, indent=2, default=str))

def print_summary(summary):
    """Print a human-readable summary."""
    print("=== CommitIQ Log Analysis Summary ===")
    print(f"Time Range: {summary['time_range']['start']} to {summary['time_range']['end']} ({summary['time_range']['duration_hours']} hours)")
    print("\nRequest Statistics:")
    print(f"  Total Requests: {summary['requests']['total']}")
    print(f"  Successful: {summary['requests']['successful']}")
    print(f"  Failed: {summary['requests']['failed']}")
    print(f"  Success Rate: {summary['requests']['success_rate_percent']}%")
    print(f"  Average Hourly Rate: {summary['requests']['hourly_rate']} requests/hour")
    
    print("\nLog Statistics:")
    print(f"  Total Logs: {summary['logs']['total']}")
    print(f"  Errors: {summary['logs']['errors']}")
    print(f"  Warnings: {summary['logs']['warnings']}")
    print(f"  Exceptions: {summary['logs']['exceptions']}")
    
    print("\nUser Statistics:")
    print(f"  Total Users: {summary['users']['total_users']}")
    print(f"  Total IPs: {summary['users']['total_ips']}")
    print("  Top Users:")
    for username, count in summary['users']['top_users']:
        print(f"    {username}: {count} requests")
    
    print("\nTop Errors:")
    for error in summary['errors']['top_errors']:
        print(f"  {error[0]}: {error[1]} occurrences")

def main():
    """Main function."""
    args = parse_args()
    
    analyzer = LogAnalyzer(args.file)
    if not analyzer.parse_logs(since=args.since, filter_str=args.filter):
        print("Failed to parse logs")
        sys.exit(1)
    
    # Handle different output options
    if args.summary:
        summary = analyzer.generate_summary()
        if args.json:
            print_json(summary)
        else:
            print_summary(summary)
    
    elif args.errors_only:
        error_logs = analyzer.get_error_logs()
        if args.json:
            print_json(error_logs)
        else:
            for log in error_logs:
                print(f"{log['timestamp']} - {log['level']} - {log['file']}:{log['line']} - {log['message']}")
    
    elif args.users > 0:
        top_users = analyzer.get_top_users(args.users)
        if args.json:
            print_json(top_users)
        else:
            print("=== Top Users ===")
            for i, user in enumerate(top_users, 1):
                print(f"{i}. {user['username']}: {user['requests']} requests from {user['unique_ips']} unique IPs")
    
    elif args.errors > 0:
        top_errors = analyzer.get_top_errors(args.errors)
        if args.json:
            print_json(top_errors)
        else:
            print("=== Top Errors ===")
            for i, error in enumerate(top_errors, 1):
                print(f"{i}. {error['error']}: {error['count']} occurrences ({error['percentage']}%)")
    
    elif args.recurring:
        recurring = analyzer.detect_recurring_errors()
        if args.json:
            print_json(recurring)
        else:
            print("=== Recurring Errors ===")
            for i, error in enumerate(recurring, 1):
                print(f"{i}. '{error['error_message']}': {error['count']} occurrences")
                print("   Examples:")
                for ex in error['examples']:
                    print(f"   - {ex['timestamp']}: {ex['message'][:100]}...")
                print()
    
    elif args.suspicious:
        suspicious = analyzer.detect_suspicious_activity()
        if args.json:
            print_json(suspicious)
        else:
            print("=== Suspicious Activity ===")
            for i, activity in enumerate(suspicious, 1):
                if activity['type'] == 'multiple_users_per_ip':
                    print(f"{i}. IP {activity['ip']} accessed {activity['user_count']} different usernames")
                    print(f"   Examples: {', '.join(activity['users'][:5])}")
                elif activity['type'] == 'high_failure_rate':
                    print(f"{i}. User {activity['username']} has high failure rate: {activity['failure_rate']}%")
                    print(f"   ({activity['failed']} failures out of {activity['requests']} requests)")
                print()
    
    else:
        # Default output - just show a basic summary
        summary = analyzer.generate_summary()
        if args.json:
            print_json(summary)
        else:
            print_summary(summary)

if __name__ == "__main__":
    main() 